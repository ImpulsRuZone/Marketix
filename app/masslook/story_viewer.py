"""
Views Telegram stories for a target peer using Telethon.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from telethon import TelegramClient
from telethon.tl.functions.stories import GetPeerStoriesRequest, ReadStoriesRequest
from telethon.errors import (
    FloodWaitError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
    UserPrivacyRestrictedError,
)

logger = logging.getLogger(__name__)


@dataclass
class StoryViewResult:
    success: bool
    stories_count: int = 0
    max_story_id: Optional[int] = None
    skipped: bool = False
    error_message: Optional[str] = None
    flood_wait_seconds: Optional[int] = None


async def view_stories(client: TelegramClient, target_url: str) -> StoryViewResult:
    """
    Fetches active stories for target_url and marks unread ones as viewed.
    target_url: @username or t.me link.
    """
    peer_ref = _normalize_target(target_url)
    if not peer_ref:
        return StoryViewResult(success=False, error_message="Пустой target_url")

    try:
        peer = await client.get_input_entity(peer_ref)
    except (UsernameInvalidError, UsernameNotOccupiedError, ValueError) as e:
        return StoryViewResult(success=False, error_message=f"Не найден: {e}")
    except Exception as e:
        return StoryViewResult(success=False, error_message=str(e))

    try:
        peer_stories = await client(GetPeerStoriesRequest(peer=peer))
    except UserPrivacyRestrictedError:
        return StoryViewResult(
            success=True,
            skipped=True,
            error_message="Приватность пользователя",
        )
    except FloodWaitError as e:
        return StoryViewResult(
            success=False,
            flood_wait_seconds=e.seconds,
            error_message=f"FloodWait {e.seconds} сек",
        )
    except Exception as e:
        return StoryViewResult(success=False, error_message=str(e))

    stories = peer_stories.stories or []
    if not stories:
        return StoryViewResult(success=True, skipped=True, error_message="Нет активных сторис")

    max_read = peer_stories.max_read_id or 0
    unread_ids = [s.id for s in stories if s.id > max_read]
    if not unread_ids:
        return StoryViewResult(success=True, skipped=True, error_message="Все сторис уже просмотрены")

    max_id = max(unread_ids)
    try:
        await client(ReadStoriesRequest(peer=peer, max_id=max_id))
    except FloodWaitError as e:
        return StoryViewResult(
            success=False,
            flood_wait_seconds=e.seconds,
            error_message=f"FloodWait {e.seconds} сек",
        )
    except Exception as e:
        return StoryViewResult(success=False, error_message=str(e))

    return StoryViewResult(
        success=True,
        stories_count=len(unread_ids),
        max_story_id=max_id,
    )


def _normalize_target(target_url: str) -> str:
    url = (target_url or "").strip()
    if not url:
        return ""
    if url.startswith("https://t.me/"):
        url = url.split("t.me/", 1)[1].split("?")[0].strip("/")
    if url.startswith("@"):
        url = url[1:]
    return url
