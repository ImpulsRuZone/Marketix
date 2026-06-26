"""
Interactive CLI for adding a new Telegram account.

Usage:
    python -m app.telegram.account_login
"""

import asyncio
import io
import sys
import logging

# Force UTF-8 for stdin/stdout to avoid encoding issues on non-UTF-8 terminals
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
if hasattr(sys.stdin, 'buffer'):
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')

from telethon import TelegramClient
from telethon.sessions import StringSession

from app.config import DATABASE_URL, DEFAULT_GPT_PROMPT
from app.database.supabase_client import init_pool, close_pool
from app.database.repositories import create_account, update_session_string
from app.logs.logger import setup_logging

logger = logging.getLogger(__name__)


def _ask(prompt: str, default: str = "") -> str:
    val = input(prompt).strip()
    return val if val else default


def _ask_int(prompt: str) -> int:
    while True:
        try:
            return int(input(prompt).strip())
        except ValueError:
            print("  Введите целое число.")


def _ask_bool(prompt: str) -> bool:
    val = input(prompt).strip().lower()
    return val in ("y", "yes", "д", "да", "1")


def _ask_choice(prompt: str, choices: list) -> str:
    print(prompt)
    for i, choice in enumerate(choices, 1):
        print(f"  {i}) {choice}")
    while True:
        try:
            idx = int(input(f"Выбери [1-{len(choices)}]: ").strip()) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        print(f"  Введи число от 1 до {len(choices)}")


def _collect_proxy() -> dict:
    print("\n--- Настройки proxy ---")
    proxy_type = _ask_choice("Тип proxy:", ["socks5", "socks4", "http"])
    proxy_host = _ask("Host (например 1.2.3.4): ")
    proxy_port = _ask_int("Port (например 1080): ")
    proxy_username = _ask("Username (Enter — пропустить): ") or None
    proxy_password = _ask("Password (Enter — пропустить): ") or None
    return {
        "proxy_enabled":  True,
        "proxy_type":     proxy_type,
        "proxy_host":     proxy_host,
        "proxy_port":     proxy_port,
        "proxy_username": proxy_username,
        "proxy_password": proxy_password,
    }


async def add_account() -> None:
    setup_logging()
    print("\n=== Добавление нового Telegram-аккаунта ===\n")

    name  = _ask("Название аккаунта (например account1): ", "account1")
    phone = _ask("Номер телефона (например +79001234567): ")

    use_proxy = _ask_bool("Использовать proxy? [y/n]: ")

    if use_proxy:
        proxy_data = _collect_proxy()
    else:
        proxy_data = {
            "proxy_enabled":  False,
            "proxy_type":     None,
            "proxy_host":     None,
            "proxy_port":     None,
            "proxy_username": None,
            "proxy_password": None,
        }

    print()
    api_id   = _ask_int("api_id (с my.telegram.org): ")
    api_hash = _ask("api_hash (с my.telegram.org): ")
    gpt_prompt = _ask(
        f"GPT prompt (Enter — стандартный):\n  [{DEFAULT_GPT_PROMPT}]\n> ",
        DEFAULT_GPT_PROMPT,
    )

    print("\nПодключаюсь к Telegram...")
    session = StringSession()
    proxy   = None
    if use_proxy:
        from app.utils.proxy_utils import build_proxy
        proxy = build_proxy({**proxy_data, "proxy_enabled": True})

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
        print(f"\nАвторизован как: {me.first_name} (id={me.id})")

    finally:
        await client.disconnect()

    print("\nСохраняю в базу данных...")
    pool = await init_pool(DATABASE_URL)
    try:
        account = await create_account(
            pool,
            name=name,
            phone=phone,
            api_id=api_id,
            api_hash=api_hash,
            gpt_prompt=gpt_prompt,
            **proxy_data,
        )
        await update_session_string(pool, account["id"], session_string)
        print(f"\n Аккаунт сохранён. ID: {account['id']}")
        print("  Запусти бота: python3 -m app.main\n")
    finally:
        await close_pool()


def main() -> None:
    asyncio.run(add_account())


if __name__ == "__main__":
    main()
