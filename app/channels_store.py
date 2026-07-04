"""Списки каналов: простой .txt файл на аккаунт (один канал = одна строка)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from app.config import AccountConfig

logger = logging.getLogger(__name__)

CHANNELS_DIR = Path("data/channels")


def _normalize_channel(value: str) -> str:
    value = (value or "").strip()
    if not value or value.startswith("#"):
        return ""
    if value.startswith("https://t.me/"):
        value = value.rsplit("/", 1)[-1]
        if not value.startswith("+"):
            value = value.lstrip("@")
    if not value.startswith("@") and not value.startswith("+"):
        value = f"@{value}"
    return value


def channel_file(account_name: str) -> Path:
    return CHANNELS_DIR / f"{account_name}.txt"


def ensure_channel_file(account_name: str) -> Path:
    """Создаёт пустой txt-файл для нового аккаунта, если его ещё нет."""
    CHANNELS_DIR.mkdir(parents=True, exist_ok=True)
    path = channel_file(account_name)
    if not path.exists():
        path.write_text(
            "# Один канал на строку. Примеры:\n"
            "# @girl_humor\n"
            "# @meow_meow_cute\n"
            "# https://t.me/+InviteHash\n",
            encoding="utf-8",
        )
        logger.info("Создан файл каналов: %s", path)
    return path


def load_channels_from_file(account_name: str) -> List[str]:
    path = channel_file(account_name)
    if not path.exists():
        return []

    channels: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        ch = _normalize_channel(line)
        if ch and ch not in channels:
            channels.append(ch)
    return channels


async def sync_accounts(accounts: List[AccountConfig], pool=None) -> None:
    """Создаёт txt-файлы для новых аккаунтов и синхронизирует с PostgreSQL."""
    from app.db import sync_channel_list, upsert_account

    for account in accounts:
        ensure_channel_file(account.name)
        channels = load_channels_from_file(account.name)

        # Поддержка старого формата: channels в accounts.json
        if not channels and account.channels:
            channels = [_normalize_channel(ch) for ch in account.channels if _normalize_channel(ch)]
            path = channel_file(account.name)
            path.write_text("\n".join(channels) + "\n", encoding="utf-8")
            logger.info("[%s] Каналы скопированы из accounts.json → %s", account.name, path)

        if pool is not None:
            await upsert_account(pool, account.name, account.phone)
            await sync_channel_list(pool, account.name, channels)


async def resolve_channels_for_account(account: AccountConfig, pool=None) -> List[str]:
    """Источник: PostgreSQL → txt-файл → accounts.json → общий список."""
    from app.joiner import MY_CHANNELS
    from app.db import get_active_channels

    if pool is not None:
        db_channels = await get_active_channels(pool, account.name)
        if db_channels:
            return db_channels

    file_channels = load_channels_from_file(account.name)
    if file_channels:
        return file_channels

    if account.channels:
        return [_normalize_channel(ch) for ch in account.channels if _normalize_channel(ch)]

    return list(MY_CHANNELS)


async def _cli() -> None:
    from app.config import DATABASE_URL, load_accounts
    from app.db import get_pool

    accounts = load_accounts("accounts.json")
    pool = None
    if DATABASE_URL:
        pool = await get_pool(DATABASE_URL)

    await sync_accounts(accounts, pool=pool)
    for account in accounts:
        count = len(load_channels_from_file(account.name))
        logger.info("[%s] %s каналов → %s", account.name, count, channel_file(account.name))


def main() -> None:
    import asyncio

    asyncio.run(_cli())


if __name__ == "__main__":
    main()
