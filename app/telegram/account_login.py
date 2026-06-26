"""
Interactive CLI for adding a new Telegram account.

Usage:
    python -m app.telegram.account_login

Flow:
    1. Enter account name (label)
    2. Enter phone number
    3. Use proxy? → if yes, enter proxy details
    4. Enter api_id
    5. Enter api_hash
    6. Enter GPT prompt (or use default)
    7. Connect to Telegram → request SMS/call code
    8. Enter confirmation code
    9. If 2FA enabled → enter password
    10. Save session_string + account to DB
"""

import asyncio
import logging

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
    try:
        val = input(prompt).strip().lower()
    except UnicodeDecodeError:
        import sys
        val = sys.stdin.buffer.readline().decode("utf-8", errors="ignore").strip().lower()
    return val in ("y", "yes", "д", "да", "1")


def _collect_proxy() -> dict:
    proxy_data = {
        "proxy_enabled":  True,
        "proxy_type":     _ask("  Тип proxy [socks5/socks4/http]: ", "socks5"),
        "proxy_host":     _ask("  Host: "),
        "proxy_port":     _ask_int("  Port: "),
        "proxy_username": _ask("  Username (Enter — пропустить): ") or None,
        "proxy_password": _ask("  Password (Enter — пропустить): ") or None,
    }
    return proxy_data


async def add_account() -> None:
    setup_logging()
    print("\n=== Добавление нового Telegram-аккаунта ===\n")

    name   = _ask("Название аккаунта (например account1): ", "account1")
    phone  = _ask("Номер телефона (например +79001234567): ")
    use_proxy = _ask_bool("Использовать proxy? [y/n]: ")

    proxy_data: dict = {}
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

    api_id   = _ask_int("api_id (с my.telegram.org): ")
    api_hash = _ask("api_hash (с my.telegram.org): ")
    gpt_prompt = _ask(
        f"GPT prompt (Enter — использовать default):\n  [{DEFAULT_GPT_PROMPT}]\n> ",
        DEFAULT_GPT_PROMPT,
    )

    print("\nПодключаюсь к Telegram...")
    session  = StringSession()
    proxy    = None
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

    # Save to DB
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
        print(f"\n✓ Аккаунт сохранён. ID: {account['id']}")
        print("  Запусти бота: python -m app.main\n")
    finally:
        await close_pool()


def main() -> None:
    asyncio.run(add_account())


if __name__ == "__main__":
    main()
