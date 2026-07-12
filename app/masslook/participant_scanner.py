"""
Scan group participants who have active stories.
"""

import logging
from typing import AsyncIterator, Optional

from telethon import TelegramClient
from telethon.tl.types import User

logger = logging.getLogger(__name__)


def user_has_stories(user: User) -> bool:
    """True if user likely has viewable stories."""
    if not isinstance(user, User):
        return False
    if user.bot or user.deleted or getattr(user, "is_self", False):
        return False
    if user.stories_unavailable or user.stories_hidden:
        return False

    stories_max = user.stories_max_id
    if not stories_max:
        return False
    if hasattr(stories_max, "max_id"):
        return stories_max.max_id is not None
    return True


def user_label(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    name = " ".join(filter(None, [user.first_name, user.last_name])).strip()
    return name or str(user.id)


async def iter_users_with_stories(
    client: TelegramClient,
    group_entity,
    *,
    limit: int = 500,
) -> AsyncIterator[User]:
    """
    Yields group participants that have active stories.
    """
    scanned = 0
    async for user in client.iter_participants(group_entity, limit=limit):
        scanned += 1
        if user_has_stories(user):
            yield user

    logger.debug("Scanned %s participants in group", scanned)
