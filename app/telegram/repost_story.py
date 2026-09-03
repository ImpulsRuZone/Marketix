"""
Repost another user's Telegram Story across active bot accounts.

Usage:
    python3 -m app.telegram.repost_story --url "https://t.me/username/s/123"
    python3 -m app.telegram.repost_story --from @username --story-id 123
    python3 -m app.telegram.repost_story --from @username --latest
    python3 -m app.telegram.repost_story --url "..." --accounts "akk1,akk2"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
from typing import List, Optional, Tuple

from telethon.errors import FloodWaitError
from telethon.tl import functions, types

from app.config import DATABASE_URL, get_telegram_api
from app.database.repositories import get_active_accounts
from app.database.supabase_client import close_pool, init_pool
from app.logs.logger import setup_logging
from app.telegram.client_factory import create_client
from app.utils.random_utils import random_delay

logger = logging.getLogger(__name__)

# https://t.me/username/s/123  or  https://telegram.me/username/s/123
_STORY_URL_RE = re.compile(
    r"(?:https?://)?(?:t\.me|telegram\.me)/([A-Za-z0-9_]+)/s/(\d+)/?",
    re.IGNORECASE,
)


def parse_story_url(url: str) -> Tuple[str, int]:
    """Extract (@)username and story_id from a public story link."""
    m = _STORY_URL_RE.search((url or "").strip())
    if not m:
        raise ValueError(
            "Неверный формат ссылки. Ожидается: https://t.me/username/s/123"
        )
    username, story_id = m.group(1), int(m.group(2))
    return f"@{username}", story_id


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Репост чужой Telegram Story на аккаунты бота")
    p.add_argument("--url", help="Ссылка вида https://t.me/username/s/123")
    p.add_argument("--from", dest="from_user", help="Автор Story: @username")
    p.add_argument("--story-id", type=int, help="ID Story автора")
    p.add_argument(
        "--latest",
        action="store_true",
        help="Взять последнюю активную Story автора (--from обязателен)",
    )
    p.add_argument(
        "--accounts",
        help="Имена аккаунтов через запятую (по умолчанию — все active)",
    )
    p.add_argument("--delay-min", type=int, default=120, help="Мин. пауза между аккаунтами (сек)")
    p.add_argument("--delay-max", type=int, default=600, help="Макс. пауза между аккаунтами (сек)")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Только проверить доступ к Story, не репостить",
    )
    return p.parse_args()


def _resolve_target(args: argparse.Namespace) -> Tuple[str, Optional[int], bool]:
    if args.url:
        username, story_id = parse_story_url(args.url)
        return username, story_id, False
    if args.from_user:
        username = args.from_user.strip()
        if not username.startswith("@"):
            username = f"@{username}"
        if args.latest:
            return username, None, True
        if args.story_id is None:
            raise SystemExit("Укажите --story-id или --latest вместе с --from")
        return username, args.story_id, False
    raise SystemExit("Укажите --url или --from + (--story-id | --latest)")


async def _latest_story_id(client, username: str) -> int:
    peer = await client.get_input_entity(username)
    result = await client(functions.stories.GetPeerStoriesRequest(peer=peer))
    stories = (result.stories.stories if result.stories else []) or []
    if not stories:
        raise RuntimeError(f"У {username} нет активных Stories")
    # Highest id ≈ newest
    story = max(stories, key=lambda s: s.id)
    return int(story.id)


async def _repost_one(
    account,
    author: str,
    story_id: int,
    dry_run: bool,
) -> Tuple[bool, str]:
    name = account.get("name") or str(account["id"])[:8]
    client = create_client(account)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            return False, "сессия недействительна"

        author_peer = await client.get_input_entity(author)

        # Ensure we can send stories as this user
        try:
            await client(functions.stories.CanSendStoryRequest(peer="me"))
        except Exception as e:
            return False, f"аккаунт не может публиковать Stories: {e}"

        if dry_run:
            return True, f"dry-run ok (story_id={story_id})"

        media = types.InputMediaStory(peer=author_peer, id=story_id)
        await client(
            functions.stories.SendStoryRequest(
                peer="me",
                media=media,
                privacy_rules=[types.InputPrivacyValueAllowAll()],
                fwd_from_id=author_peer,
                fwd_from_story=story_id,
            )
        )
        return True, "репост отправлен"
    except FloodWaitError as e:
        wait = int(e.seconds) + 15
        logger.warning("[%s] FloodWait %s сек — жду", name, e.seconds)
        await asyncio.sleep(wait)
        return False, f"FloodWait {e.seconds} сек"
    except Exception as e:
        return False, str(e)
    finally:
        await client.disconnect()


async def main() -> None:
    setup_logging()
    args = _parse_args()
    author, story_id, use_latest = _resolve_target(args)

    get_telegram_api()
    if not DATABASE_URL:
        raise SystemExit("DATABASE_URL не задан в .env")

    pool = await init_pool(DATABASE_URL)
    try:
        accounts = await get_active_accounts(pool)
        # Respect account_settings.is_active when present
        accounts = [
            a for a in accounts
            if a.get("is_active") is None or a.get("is_active") is True
        ]

        if args.accounts:
            wanted = {n.strip() for n in args.accounts.split(",") if n.strip()}
            accounts = [
                a for a in accounts
                if (a.get("name") or "") in wanted or (a.get("phone") or "") in wanted
            ]

        if not accounts:
            raise SystemExit("Нет подходящих active-аккаунтов")

        # Resolve --latest using the first account
        if use_latest:
            probe = create_client(accounts[0])
            try:
                await probe.connect()
                if not await probe.is_user_authorized():
                    raise SystemExit(
                        f"Аккаунт {accounts[0].get('name')} не авторизован — "
                        "нужен для --latest"
                    )
                story_id = await _latest_story_id(probe, author)
                print(f"Последняя Story {author}: id={story_id}", flush=True)
            finally:
                await probe.disconnect()

        assert story_id is not None
        print(
            f"Репост {author}/s/{story_id} → {len(accounts)} аккаунт(ов)"
            + (" [dry-run]" if args.dry_run else ""),
            flush=True,
        )

        ok_n = fail_n = 0
        for i, account in enumerate(accounts):
            name = account.get("name") or str(account["id"])[:8]
            print(f"\n[{i + 1}/{len(accounts)}] {name} ...", flush=True)
            ok, msg = await _repost_one(account, author, story_id, args.dry_run)
            if ok:
                ok_n += 1
                print(f"  OK: {msg}", flush=True)
            else:
                fail_n += 1
                print(f"  FAIL: {msg}", flush=True)

            if i < len(accounts) - 1 and not args.dry_run:
                delay = random_delay(args.delay_min, args.delay_max)
                print(f"  Пауза {delay} сек...", flush=True)
                await asyncio.sleep(delay)

        print(f"\nГотово: ok={ok_n}, fail={fail_n}", flush=True)
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
