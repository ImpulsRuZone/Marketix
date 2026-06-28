"""
Entry point. Loads all active accounts from the DB and runs them in parallel.

Usage:
    python -m app.main                  # спросит про вступление (если TTY)
    python -m app.main --join             # вступить в новые каналы
    python -m app.main --no-join          # только слушать посты

To add a new account first:
    python -m app.telegram.account_login
"""

import argparse
import asyncio
import logging

from app.config import DATABASE_URL, get_telegram_api
from app.database.supabase_client import init_pool, close_pool
from app.database.repositories import get_active_accounts
from app.telegram.account_worker import AccountWorker
from app.logs.logger import setup_logging
from app.startup_options import resolve_join_on_startup

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Neurocomment Telegram Bot")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--join",
        action="store_true",
        help="вступить в каналы из target_chats, где аккаунт ещё не состоит",
    )
    group.add_argument(
        "--no-join",
        action="store_true",
        help="не вступать в новые каналы, работать с текущим списком",
    )
    return parser.parse_args()


async def main() -> None:
    setup_logging()
    args = _parse_args()

    cli_join = None
    if args.join:
        cli_join = True
    elif args.no_join:
        cli_join = False

    join_on_startup = resolve_join_on_startup(cli_join)
    logger.info(
        "Режим вступления: %s",
        "включён" if join_on_startup else "выключен (только прослушивание)",
    )

    if not DATABASE_URL:
        logger.critical("DATABASE_URL не задан. Проверьте файл .env.")
        return

    try:
        get_telegram_api()
    except RuntimeError as e:
        logger.critical(str(e))
        return

    pool = await init_pool(DATABASE_URL)

    try:
        accounts = await get_active_accounts(pool)
        if not accounts:
            logger.warning(
                "В БД нет активных аккаунтов. "
                "Добавьте аккаунт: python3 -m app.telegram.account_login"
            )
            return

        logger.info(f"Загружено активных аккаунтов: {len(accounts)}")

        workers = [
            AccountWorker(account, pool, join_on_startup=join_on_startup)
            for account in accounts
        ]
        await asyncio.gather(*(w.run() for w in workers))

    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
