#!/usr/bin/env python3
"""
Replace target_chats in PostgreSQL with channels from seeds/channels CSV.

Usage:
    python3 scripts/import_channels_from_csv.py
    python3 scripts/import_channels_from_csv.py --csv seeds/channels/telegram_auto_moto_database.csv
    python3 scripts/import_channels_from_csv.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
from pathlib import Path

from app.config import DATABASE_URL
from app.database import repositories as repo
from app.database.supabase_client import close_pool, init_pool

logger = logging.getLogger(__name__)

DEFAULT_CSV = Path("seeds/channels/telegram_auto_moto_database.csv")
DEFAULT_JSON = Path("seeds/channels/target_channels.json")


def normalize_url(link: str, username: str) -> str:
    link = (link or "").strip()
    username = (username or "").strip()
    if link.startswith("https://t.me/joinchat/"):
        return link
    if username and username.startswith("joinchat/"):
        return f"https://t.me/{username}"
    if username and not username.startswith("+"):
        return f"@{username.lstrip('@')}"
    if link.startswith("https://t.me/"):
        part = link.rstrip("/").split("/")[-1]
        if part.startswith("+"):
            return link
        return f"@{part}"
    return link


def load_channels_from_csv(csv_path: Path) -> list[dict]:
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    channels: list[dict] = []
    seen: set[str] = set()

    for row in rows:
        if row.get("Тип", "").strip() != "канал":
            continue

        chat_url = normalize_url(row.get("Ссылка", ""), row.get("Username / invite", ""))
        if not chat_url or chat_url in seen:
            continue
        seen.add(chat_url)

        username = (row.get("Username / invite") or "").strip().lstrip("@")
        if username.startswith("joinchat"):
            username = ""

        channels.append(
            {
                "chat_url": chat_url,
                "title": (row.get("Название") or "").strip(),
                "username": username or None,
                "category": (row.get("Основная категория") or "").strip(),
            }
        )
    return channels


def load_channels_from_json(json_path: Path) -> list[dict]:
    return json.loads(json_path.read_text(encoding="utf-8"))


async def replace_channels(pool, channels: list[dict], dry_run: bool = False) -> dict:
    if dry_run:
        active = await repo.get_active_target_chats(pool)
        return {
            "dry_run": True,
            "current_active": len(active),
            "new_channels": len(channels),
        }

    return await repo.replace_target_chats(pool, channels)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.json.exists():
        channels = load_channels_from_json(args.json)
        logger.info("Loaded %s channels from %s", len(channels), args.json)
    elif args.csv.exists():
        channels = load_channels_from_csv(args.csv)
        logger.info("Loaded %s channels from %s", len(channels), args.csv)
    else:
        raise SystemExit(f"Channel list not found: {args.json} or {args.csv}")

    if not DATABASE_URL:
        raise SystemExit("DATABASE_URL is not set. Add it to .env")

    pool = await init_pool(DATABASE_URL)
    try:
        result = await replace_channels(pool, channels, dry_run=args.dry_run)
        if args.dry_run:
            print(
                f"Dry run: active now={result['current_active']}, "
                f"will import={result['new_channels']}"
            )
        else:
            print(
                "Done: deactivated=%(deactivated)s, inserted=%(inserted)s, "
                "account_chats_cleared=%(account_chats_cleared)s"
                % result
            )
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
