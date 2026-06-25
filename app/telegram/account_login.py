from __future__ import annotations

import locale
import sys
from datetime import datetime
from getpass import getpass
from pathlib import Path
from typing import Any

from telethon import TelegramClient
from telethon.errors import (
    ApiIdInvalidError,
    AuthRestartError,
    FloodWaitError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberBannedError,
    PhoneNumberFloodError,
    PhoneNumberInvalidError,
    PhoneNumberUnoccupiedError,
    SendCodeUnavailableError,
)
from telethon.sessions import StringSession

from app.db.repositories import AccountRepository, ChatRepository, SettingsRepository
from app.settings.settings_manager import SettingsManager


def _decode_user_input(raw: bytes) -> str:
    encodings: list[str] = []
    if sys.stdin.encoding:
        encodings.append(sys.stdin.encoding)
    preferred = locale.getpreferredencoding(False)
    if preferred:
        encodings.append(preferred)
    encodings.extend(["utf-8", "cp1251"])

    tried: set[str] = set()
    for encoding in encodings:
        if encoding in tried:
            continue
        tried.add(encoding)
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _ask_text(question: str, default: str | None = None) -> str:
    suffix = f" (по умолчанию: {default})" if default is not None else ""
    print(f"{question}{suffix}: ", end="", flush=True)
    raw = sys.stdin.buffer.readline()
    if not raw:
        raise EOFError(f"Не получен ввод для поля: {question}")
    value = _decode_user_input(raw).strip()
    if not value and default is not None:
        return default
    return value


def _ask_bool(question: str) -> bool:
    return _ask_text(f"{question} [д/н]", default="н").lower() in {"y", "yes", "д", "да"}


def _ask_int(question: str, default: int | None = None) -> int:
    raw = _ask_text(question, default=str(default) if default is not None else None)
    return int(raw)


def _build_account_name(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    short = digits[-4:] if len(digits) >= 4 else digits or "new"
    return f"account_{short}"


def _build_runtime_proxy(proxy_cfg: dict[str, Any] | None) -> tuple | None:
    if not proxy_cfg or not proxy_cfg.get("proxy_enabled"):
        return None

    import socks

    proxy_type = proxy_cfg["proxy_type"].lower()
    proxy_map = {"socks5": socks.SOCKS5, "socks4": socks.SOCKS4, "http": socks.HTTP}
    if proxy_type not in proxy_map:
        raise ValueError("proxy_type must be socks5/socks4/http")

    return (
        proxy_map[proxy_type],
        proxy_cfg["proxy_host"],
        int(proxy_cfg["proxy_port"]),
        True,
        proxy_cfg.get("proxy_username"),
        proxy_cfg.get("proxy_password"),
    )


def _build_onboarding_session_name(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit()) or "new"
    session_dir = Path("data")
    session_dir.mkdir(parents=True, exist_ok=True)
    return str(session_dir / f"session_{digits}")


async def _sign_in_with_start(client: TelegramClient, phone: str) -> None:
    def code_callback() -> str:
        return _ask_text("Введите код подтверждения Telegram")

    def password_callback() -> str:
        return getpass("Введите пароль Telegram 2FA: ")

    print("Запрашиваю код авторизации Telegram...")
    print("Проверьте сервисный чат Telegram и архив чатов в приложении.")

    try:
        await client.start(
            phone=phone,
            code_callback=code_callback,
            password=password_callback,
            max_attempts=5,
        )
    except ApiIdInvalidError:
        raise RuntimeError("Неверный API ID или API hash. Проверьте данные из my.telegram.org.") from None
    except PhoneNumberInvalidError:
        raise RuntimeError("Неверный формат телефона. Используйте международный формат, например +79991234567.") from None
    except PhoneNumberUnoccupiedError:
        raise RuntimeError("Этот номер не зарегистрирован в Telegram.") from None
    except PhoneNumberBannedError:
        raise RuntimeError("Номер заблокирован в Telegram. Авторизация через API невозможна.") from None
    except PhoneNumberFloodError:
        raise RuntimeError(
            "Слишком много попыток для этого номера. Telegram временно ограничил отправку кода."
        ) from None
    except AuthRestartError:
        raise RuntimeError("Telegram попросил перезапустить авторизацию. Запустите onboarding снова.") from None
    except SendCodeUnavailableError:
        raise RuntimeError(
            "Telegram временно не может отправить код для этого номера. "
            "Подождите несколько минут и повторите onboarding."
        ) from None
    except PhoneCodeInvalidError:
        raise RuntimeError("Введен неверный код подтверждения Telegram.") from None
    except PhoneCodeExpiredError:
        raise RuntimeError("Код подтверждения истек. Запустите onboarding заново.") from None
    except FloodWaitError as exc:
        raise RuntimeError(f"Слишком много попыток. Подождите {exc.seconds} секунд.") from None
    except AuthRestartError:
        raise RuntimeError("Telegram попросил перезапустить авторизацию. Запустите onboarding снова.") from None


async def onboard_account_cli(
    account_repo: AccountRepository,
    settings_repo: SettingsRepository,
    chat_repo: ChatRepository,
) -> str:
    """Interactive account onboarding flow.

    Order is intentionally strict:
    1) phone number
    2) proxy usage decision
    3) api_id/api_hash
    4) Telegram login code (manual)
    5) optional 2FA password
    6) account settings and target chats
    """

    phone = _ask_text("Введите номер телефона (международный формат)")
    name = _ask_text("Введите имя аккаунта", default=_build_account_name(phone))
    prompt = _ask_text("Введите промпт для этого аккаунта")

    proxy_cfg: dict[str, Any] = {"proxy_enabled": False}
    if _ask_bool("Использовать прокси перед подключением к Telegram?"):
        proxy_cfg = {
            "proxy_enabled": True,
            "proxy_type": _ask_text("Тип прокси [socks5/socks4/http]").lower(),
            "proxy_host": _ask_text("Хост прокси"),
            "proxy_port": _ask_int("Порт прокси"),
            "proxy_username": _ask_text("Логин прокси (необязательно)") or None,
            "proxy_password": getpass("Пароль прокси (необязательно): ").strip() or None,
        }

    api_id = _ask_int("Введите Telegram API ID")
    api_hash = _ask_text("Введите Telegram API hash")

    proxy = _build_runtime_proxy(proxy_cfg)
    session_name = _build_onboarding_session_name(phone)
    client = TelegramClient(session_name, api_id=api_id, api_hash=api_hash, proxy=proxy)

    try:
        await _sign_in_with_start(client=client, phone=phone)
        session_string = StringSession.save(client.session)
    finally:
        await client.disconnect()

    account = account_repo.upsert_account(
        {
            "phone": phone,
            "name": name,
            "api_id": api_id,
            "api_hash": api_hash,
            "session_string": session_string,
            "gpt_prompt": prompt,
            "status": "active",
            **proxy_cfg,
            "updated_at": datetime.utcnow().isoformat(),
        }
    )
    account_id = account["id"]

    daily_comment_percent = _ask_int("Процент комментирования в день [0-100]", default=30)
    max_comments_per_day = _ask_int("Максимум комментариев в день", default=20)
    sleep_start_time = _ask_text("Время начала сна [HH:MM], например 01:00", default="01:00")
    sleep_end_time = _ask_text("Время окончания сна [HH:MM], например 08:00", default="08:00")
    timezone = _ask_text("Часовой пояс, например Europe/Moscow", default="UTC")
    join_delay_min = _ask_int("Минимальная задержка входа в чаты (сек)", default=120)
    join_delay_max = _ask_int("Максимальная задержка входа в чаты (сек)", default=600)
    comment_delay_min = _ask_int("Минимальная задержка перед комментарием (сек)", default=30)
    comment_delay_max = _ask_int("Максимальная задержка перед комментарием (сек)", default=180)

    SettingsManager.validate_comment_limits(daily_comment_percent, max_comments_per_day)
    SettingsManager.validate_delays(join_delay_min, join_delay_max, "join_delay")
    SettingsManager.validate_delays(comment_delay_min, comment_delay_max, "comment_delay")

    settings_repo.upsert_settings(
        {
            "account_id": account_id,
            "daily_comment_percent": daily_comment_percent,
            "max_comments_per_day": max_comments_per_day,
            "sleep_start_time": sleep_start_time,
            "sleep_end_time": sleep_end_time,
            "timezone": timezone,
            "join_delay_min_seconds": join_delay_min,
            "join_delay_max_seconds": join_delay_max,
            "comment_delay_min_seconds": comment_delay_min,
            "comment_delay_max_seconds": comment_delay_max,
            "is_active": True,
        }
    )

    target_chats = _ask_text("Целевые чаты (ссылки/username через запятую)", default="")
    for item in [x.strip() for x in target_chats.split(",") if x.strip()]:
        chat = chat_repo.upsert_target_chat({"chat_url": item, "is_active": True})
        chat_repo.upsert_account_chat(
            {
                "account_id": account_id,
                "chat_id": chat["id"],
                "status": "pending",
            }
        )

    return account_id
