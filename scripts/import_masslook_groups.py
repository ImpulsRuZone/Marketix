#!/usr/bin/env python3
"""
Import masslook groups from a text file (one link/@username per line).

Usage:
    python scripts/import_masslook_groups.py groups.txt
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import DATABASE_URL
from app.database.supabase_client import init_pool, close_pool
from app.database.repositories import upsert_masslook_group


async def main(path: Path) -> None:
    if not DATABASE_URL:
        print("DATABASE_URL не задан в .env")
        sys.exit(1)

    lines = [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    if not lines:
        print("Файл пуст")
        return

    pool = await init_pool(DATABASE_URL)
    try:
        for line in lines:
            row = await upsert_masslook_group(pool, line)
            print(f"OK: {row['group_url']}")
        print(f"Импортировано: {len(lines)}")
    finally:
        await close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import masslook groups")
    parser.add_argument("file", type=Path, help="Text file with group links")
    asyncio.run(main(parser.parse_args().file))
