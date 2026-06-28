"""
Entry point. Loads all active accounts from the DB and runs them in parallel.

Usage:
    python -m app.main

To add a new account first:
    python -m app.telegram.account_login
"""

import asyncio
import logging

from app.config import DATABASE_URL, get_telegram_api
from app.database.supabase_client import init_pool, close_pool
from app.database.repositories import get_active_accounts
from app.telegram.account_worker import AccountWorker
from app.logs.logger import setup_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()

    if not DATABASE_URL:
        logger.critical("DATABASE_URL is not set. Check your .env file.")
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
                "No active accounts found in DB. "
                "Add one with: python -m app.telegram.account_login"
            )
            return

        logger.info(f"Loaded {len(accounts)} active account(s)")

        workers = [AccountWorker(account, pool) for account in accounts]
        await asyncio.gather(*(w.run() for w in workers))

    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
