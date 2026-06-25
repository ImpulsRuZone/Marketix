from __future__ import annotations

from datetime import datetime
from getpass import getpass
from typing import Any

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

from app.db.repositories import AccountRepository, ChatRepository, SettingsRepository
from app.settings.settings_manager import SettingsManager


def _ask_bool(question: str) -> bool:
    return input(f"{question} [y/N]: ").strip().lower() in {"y", "yes"}


def _ask_int(question: str, default: int | None = None) -> int:
    raw = input(f"{question}{f' (default: {default})' if default is not None else ''}: ").strip()
    if not raw and default is not None:
        return default
    return int(raw)


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

    phone = input("Phone number (international format): ").strip()
    name = input("Account display name: ").strip()
    prompt = input("Per-account GPT prompt: ").strip()

    proxy_cfg: dict[str, Any] = {"proxy_enabled": False}
    if _ask_bool("Use proxy before Telegram connection?"):
        proxy_cfg = {
            "proxy_enabled": True,
            "proxy_type": input("Proxy type [socks5/socks4/http]: ").strip().lower(),
            "proxy_host": input("Proxy host: ").strip(),
            "proxy_port": _ask_int("Proxy port"),
            "proxy_username": input("Proxy username (optional): ").strip() or None,
            "proxy_password": getpass("Proxy password (optional): ").strip() or None,
        }

    api_id = _ask_int("Telegram API ID")
    api_hash = input("Telegram API hash: ").strip()

    proxy = _build_runtime_proxy(proxy_cfg)
    client = TelegramClient(StringSession(), api_id=api_id, api_hash=api_hash, proxy=proxy)

    await client.connect()
    try:
        await client.send_code_request(phone=phone)
        login_code = input("Telegram login code: ").strip()
        try:
            await client.sign_in(phone=phone, code=login_code)
        except SessionPasswordNeededError:
            password = getpass("Telegram 2FA password: ")
            await client.sign_in(password=password)

        session_string = client.session.save()
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

    daily_comment_percent = _ask_int("daily_comment_percent [0-100]", default=30)
    max_comments_per_day = _ask_int("max_comments_per_day", default=20)
    sleep_start_time = input("sleep_start_time [HH:MM], e.g. 01:00: ").strip() or "01:00"
    sleep_end_time = input("sleep_end_time [HH:MM], e.g. 08:00: ").strip() or "08:00"
    timezone = input("timezone, e.g. Europe/Moscow (default UTC): ").strip() or "UTC"
    join_delay_min = _ask_int("join_delay_min_seconds", default=120)
    join_delay_max = _ask_int("join_delay_max_seconds", default=600)
    comment_delay_min = _ask_int("comment_delay_min_seconds", default=30)
    comment_delay_max = _ask_int("comment_delay_max_seconds", default=180)

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

    target_chats = input("Target chats (comma-separated links/usernames): ").strip()
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
