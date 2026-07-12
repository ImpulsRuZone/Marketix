"""
Entry point for mass-looking (story viewing).

Usage:
    python -m app.masslook.main

Enable per account in Supabase:
    UPDATE account_settings SET masslook_enabled = true WHERE account_id = '...';

Add targets:
    INSERT INTO story_targets (target_url) VALUES ('@username');
"""

import asyncio
import logging

from app.config import DATABASE_URL, get_telegram_api
from app.database.supabase_client import init_pool, close_pool
from app.database.repositories import get_active_accounts, sync_account_settings
from app.masslook.worker import MasslookWorker
from app.logs.logger import setup_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()

    if not DATABASE_URL:
        logger.critical("DATABASE_URL не задан. Проверьте .env")
        return

    try:
        get_telegram_api()
    except RuntimeError as e:
        logger.critical(str(e))
        return

    pool = await init_pool(DATABASE_URL)

    try:
        await sync_account_settings(pool)
        accounts = await get_active_accounts(pool)
        if not accounts:
            logger.warning(
                "Нет активных аккаунтов. "
                "Добавьте: python3 -m app.telegram.account_login"
            )
            return

        enabled = [
            a for a in accounts
            if a.get("masslook_enabled")
        ]
        if not enabled:
            logger.warning(
                "Нет аккаунтов с masslook_enabled=true. "
                "Включите в account_settings (Supabase)."
            )
            return

        logger.info(
            f"Масслукинг: {len(enabled)} аккаунт(ов) из {len(accounts)}"
        )

        workers = [MasslookWorker(account, pool) for account in enabled]
        await asyncio.gather(*(w.run() for w in workers))

    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
