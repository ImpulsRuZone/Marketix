"""
View and like Telegram stories for a user.
"""

import logging
from dataclasses import dataclass
from typing import Optional, Union

from telethon import TelegramClient
from telethon.tl.functions.stories import (
    GetPeerStoriesRequest,
    ReadStoriesRequest,
    SendReactionRequest,
)
from telethon.tl.types import ReactionEmoji, User
from telethon.errors import (
    FloodWaitError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
    UserPrivacyRestrictedError,
)

logger = logging.getLogger(__name__)

DEFAULT_REACTION = "❤️"


@dataclass
class StoryActionResult:
    success: bool
    stories_count: int = 0
    liked_count: int = 0
    max_story_id: Optional[int] = None
    skipped: bool = False
    error_message: Optional[str] = None
    flood_wait_seconds: Optional[int] = None


async def view_and_like_stories(
    client: TelegramClient,
    user: Union[User, str, int],
    *,
    like_enabled: bool = True,
    reaction_emoji: str = DEFAULT_REACTION,
) -> StoryActionResult:
    """
    Views unread stories and sends a like reaction on each active story.
    user: User entity, @username, or user id.
    """
    try:
        peer = await client.get_input_entity(user)
    except (UsernameInvalidError, UsernameNotOccupiedError, ValueError) as e:
        return StoryActionResult(success=False, error_message=f"Не найден: {e}")
    except Exception as e:
        return StoryActionResult(success=False, error_message=str(e))

    try:
        peer_stories = await client(GetPeerStoriesRequest(peer=peer))
    except UserPrivacyRestrictedError:
        return StoryActionResult(
            success=True,
            skipped=True,
            error_message="Приватность пользователя",
        )
    except FloodWaitError as e:
        return StoryActionResult(
            success=False,
            flood_wait_seconds=e.seconds,
            error_message=f"FloodWait {e.seconds} сек",
        )
    except Exception as e:
        return StoryActionResult(success=False, error_message=str(e))

    stories = peer_stories.stories or []
    if not stories:
        return StoryActionResult(success=True, skipped=True, error_message="Нет активных сторис")

    max_read = peer_stories.max_read_id or 0
    unread_ids = [s.id for s in stories if s.id > max_read]

    if unread_ids:
        max_id = max(unread_ids)
        try:
            await client(ReadStoriesRequest(peer=peer, max_id=max_id))
        except FloodWaitError as e:
            return StoryActionResult(
                success=False,
                flood_wait_seconds=e.seconds,
                error_message=f"FloodWait {e.seconds} сек",
            )
        except Exception as e:
            return StoryActionResult(success=False, error_message=str(e))
    else:
        max_id = max(s.id for s in stories)

    liked_count = 0
    if like_enabled:
        emoji = reaction_emoji or DEFAULT_REACTION
        for story in stories:
            try:
                await client(SendReactionRequest(
                    peer=peer,
                    story_id=story.id,
                    reaction=ReactionEmoji(emoticon=emoji),
                    add_to_recent=True,
                ))
                liked_count += 1
            except FloodWaitError as e:
                return StoryActionResult(
                    success=liked_count > 0 or bool(unread_ids),
                    stories_count=len(unread_ids) or len(stories),
                    liked_count=liked_count,
                    max_story_id=max_id,
                    flood_wait_seconds=e.seconds,
                    error_message=f"FloodWait {e.seconds} сек",
                )
            except Exception as e:
                logger.debug("Like failed for story %s: %s", story.id, e)

    viewed_count = len(unread_ids) if unread_ids else 0
    if not viewed_count and not liked_count:
        return StoryActionResult(
            success=True,
            skipped=True,
            error_message="Сторис уже просмотрены, лайки не поставлены",
        )

    return StoryActionResult(
        success=True,
        stories_count=viewed_count or len(stories),
        liked_count=liked_count,
        max_story_id=max_id,
    )
