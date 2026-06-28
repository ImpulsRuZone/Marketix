"""
Interactive CLI for adding a new Telegram account.

Usage:
    python3 -m app.telegram.account_login

Flow:
    1. Account name
    2. Proxy settings + connection test
    3. GPT prompt
    4. Phone number
    5. Telegram auth (code + optional 2FA)
    6. Save to DB

API_ID / API_HASH берутся из .env (одна пара на все аккаунты).
"""

import asyncio
import logging
import sys

from telethon import TelegramClient
from telethon.sessions import StringSession

from app.config import DATABASE_URL, DEFAULT_GPT_PROMPT, get_telegram_api
from app.database.supabase_client import init_pool, close_pool
from app.database.repositories import create_account
from app.logs.logger import setup_logging

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Low-level input helpers (bypass encoding issues)
# ──────────────────────────────────────────────

def _normalize(val: str) -> str:
    return val.strip().replace("\r", "").replace("\ufeff", "")


def _readline() -> str:
    """Read a line from stdin robustly, regardless of terminal encoding."""
    raw = sys.stdin.buffer.readline()
    for enc in ("utf-8", "cp1251", "latin-1"):
        try:
            return _normalize(raw.decode(enc))
        except UnicodeDecodeError:
            continue
    return _normalize(raw.decode("latin-1", errors="replace"))


def _ask(prompt: str, default: str = "") -> str:
    sys.stdout.write(prompt)
    sys.stdout.flush()
    val = _readline()
    return val if val else default


def _ask_int(prompt: str) -> int:
    while True:
        raw = _ask(prompt)
        try:
            return int(raw)
        except ValueError:
            print("  Введите целое число.", flush=True)


def _ask_bool(prompt: str) -> bool:
    val = _normalize(_ask(prompt)).lower()
    if not val:
        return False
    if val[0] in ("y", "д", "1") or val in ("yes", "да"):
        return True
    if val[0] in ("n", "н", "0") or val in ("no", "нет"):
        return False
    return val.startswith("y") or val.startswith("д")


def _ask_choice(prompt: str, choices: list) -> str:
    while True:
        print(f"\n{prompt}", flush=True)
        for i, c in enumerate(choices, 1):
            print(f"  {i}) {c}", flush=True)
        raw = _ask(f"Выбери [1-{len(choices)}]: ")
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            if raw in choices:
                return raw
        print(f"  Нужно число от 1 до {len(choices)}", flush=True)


# ──────────────────────────────────────────────
# Proxy test
# ──────────────────────────────────────────────

async def _test_proxy(proxy_type: str, host: str, port: int,
                      username=None, password=None) -> bool:
    """Tests TCP connectivity to Telegram through the proxy."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _test_proxy_sync,
                                      proxy_type, host, port, username, password)


def _test_proxy_sync(proxy_type: str, host: str, port: int,
                     username=None, password=None) -> bool:
    """Test proxy by opening a TCP connection to Telegram DC1 through it."""
    try:
        import socks
        type_map = {"socks5": socks.SOCKS5, "socks4": socks.SOCKS4, "http": socks.HTTP}
        s = socks.socksocket()
        s.set_proxy(type_map.get(proxy_type.lower(), socks.SOCKS5),
                    host, port, True, username, password)
        s.settimeout(10)
        s.connect(("149.154.167.51", 443))
        s.close()
        return True
    except ImportError:
        pass
    except Exception as e:
        print(f"  [!] Ошибка (PySocks): {e}", flush=True)
        return False

    # Fallback: plain TCP to proxy host to at least check it's reachable
    try:
        import socket
        s = socket.create_connection((host, port), timeout=10)
        s.close()
        print("  [~] Порт proxy открыт, но маршрут через него не проверен.", flush=True)
        return True
    except Exception as e:
        print(f"  [!] Ошибка: {e}", flush=True)
        return False


# ──────────────────────────────────────────────
# Main flow
# ──────────────────────────────────────────────

async def add_account() -> None:
    setup_logging()
    print("\n=== Добавление нового Telegram-аккаунта ===\n", flush=True)

    try:
        api_id, api_hash = get_telegram_api()
        print(f"  API_ID: {api_id} (из .env, общий для всех аккаунтов)\n", flush=True)
    except RuntimeError as e:
        print(f"\n[ОШИБКА] {e}\n", flush=True)
        return

    # 1. Account name
    name = _ask("Название аккаунта (например account1): ", "account1")

    # 2. Proxy (меню с цифрами — надёжнее чем y/n в SSH)
    print("\nИспользовать proxy?", flush=True)
    print("  1) Да", flush=True)
    print("  2) Нет", flush=True)
    proxy_answer = _ask("Выбери [1-2]: ")
    use_proxy = proxy_answer == "1" or _normalize(proxy_answer).lower() in ("да", "y", "yes")

    if use_proxy:
        print("\n--- Настройки proxy ---", flush=True)
        proxy_type = _ask_choice("Тип proxy:", ["socks5", "socks4", "http"])
        proxy_host = _ask("Host (IP или домен): ")
        proxy_port = _ask_int("Port: ")
        proxy_username = _ask("Username (Enter — пропустить): ") or None
        proxy_password = _ask("Password (Enter — пропустить): ") or None

        print("\nТестирую подключение через proxy...", flush=True)
        ok = await _test_proxy(proxy_type, proxy_host, proxy_port, proxy_username, proxy_password)
        if ok:
            print("  [OK] Proxy работает — соединение с Telegram установлено.", flush=True)
        else:
            print("  [ОШИБКА] Proxy недоступен.", flush=True)
            if not _ask_bool("  Продолжить без проверки proxy? [y/n]: "):
                print("Отменено.", flush=True)
                return

        proxy_data = {
            "proxy_enabled":  True,
            "proxy_type":     proxy_type,
            "proxy_host":     proxy_host,
            "proxy_port":     proxy_port,
            "proxy_username": proxy_username,
            "proxy_password": proxy_password,
        }
    else:
        print("  Proxy отключён.", flush=True)
        proxy_data = {
            "proxy_enabled":  False,
            "proxy_type":     None,
            "proxy_host":     None,
            "proxy_port":     None,
            "proxy_username": None,
            "proxy_password": None,
        }

    # 3. GPT prompt
    print(flush=True)
    gpt_prompt = _ask(
        f"GPT prompt (Enter — стандартный):\n  [{DEFAULT_GPT_PROMPT}]\n> ",
        DEFAULT_GPT_PROMPT,
    )

    # 4. Phone number
    print(flush=True)
    phone = _ask("Номер телефона (например +79001234567): ")

    # 5. Telegram auth
    print("\nПодключаюсь к Telegram...", flush=True)
    session = StringSession()
    proxy   = None
    if use_proxy:
        from app.utils.proxy_utils import build_proxy, proxy_label, verify_proxy_backend
        proxy = build_proxy({**proxy_data, "proxy_enabled": True})
        ok_backend, backend_msg = verify_proxy_backend()
        print(f"  [PROXY] Маршрут: {proxy_label(proxy)} -> Telegram", flush=True)
        print(f"  [PROXY] {backend_msg}", flush=True)
        if not ok_backend:
            cont = _ask_bool("  Proxy не будет работать. Продолжить? [y/n]: ")
            if not cont:
                print("Отменено.", flush=True)
                return

    client = TelegramClient(session, api_id, api_hash, proxy=proxy)

    try:
        await client.connect()

        if not await client.is_user_authorized():
            await client.send_code_request(phone)
            code = _ask("Введи код из Telegram/SMS: ")
            try:
                await client.sign_in(phone, code)
            except Exception as e:
                if "Two-steps" in str(e) or "password" in str(e).lower():
                    password = _ask("Введи пароль 2FA: ")
                    await client.sign_in(password=password)
                else:
                    raise

        me = await client.get_me()
        session_string = client.session.save()
        print(f"\n  Авторизован как: {me.first_name} (id={me.id})", flush=True)

    finally:
        await client.disconnect()

    # 6. Save to DB
    print("\nСохраняю в базу данных...", flush=True)
    pool = await init_pool(DATABASE_URL)
    try:
        account = await create_account(
            pool,
            name=name,
            phone=phone,
            session_string=session_string,
            gpt_prompt=gpt_prompt,
            **proxy_data,
        )
        print(f"\n[OK] Аккаунт '{name}' сохранён. ID: {account['id']}", flush=True)
        print("     Запусти бота: python3 -m app.main\n", flush=True)
    finally:
        await close_pool()


def main() -> None:
    asyncio.run(add_account())


if __name__ == "__main__":
    main()
