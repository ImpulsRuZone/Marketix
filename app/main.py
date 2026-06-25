"""
Точка входа. Загружает все аккаунты из accounts.json
и запускает их параллельно.
"""

import asyncio
import logging

from app.config import load_accounts, DATABASE_URL
from app.db import get_pool
from app.account_bot import AccountBot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_account(bot: AccountBot) -> None:
    """Запускает один аккаунт с перезапуском при неожиданном отключении."""
    while True:
        try:
            await bot.start()
        except Exception as e:
            logger.error(f"[{bot.cfg.name}] Упал с ошибкой: {e}. Перезапуск через 30 сек...")
            await asyncio.sleep(30)


async def main() -> None:
    accounts = load_accounts("accounts.json")
    logger.info(f"Загружено аккаунтов: {len(accounts)}")

    pool = None
    if DATABASE_URL:
        pool = await get_pool(DATABASE_URL)
        logger.info("Подключение к БД установлено")
    else:
        logger.warning("DATABASE_URL не задан — логирование в БД отключено")

    bots = [AccountBot(cfg, pool) for cfg in accounts]

    await asyncio.gather(*(run_account(bot) for bot in bots))


if __name__ == "__main__":
    asyncio.run(main())
