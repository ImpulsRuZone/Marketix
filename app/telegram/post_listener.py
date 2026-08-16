"""
Registers a NewMessage event handler on the client.
Passes new channel posts to the comment pipeline.
"""

import logging
from typing import Callable, Set

from telethon import TelegramClient, events

from app.config import MIN_POST_LENGTH
from app.telegram.chat_utils import peer_id

logger = logging.getLogger(__name__)


def register_post_handler(
    client: TelegramClient,
    monitored_ids: Set[int],
    on_new_post: Callable,
) -> None:
    """
    Registers an event handler that fires for every new channel post
    in the monitored peer-id set.
    """

    @client.on(events.NewMessage(incoming=True))
    async def _handler(event: events.NewMessage.Event) -> None:
        if not event.is_channel:
            return

        if event.chat_id not in monitored_ids:
            return

        if not event.message.post:
            return

        text = event.message.text
        if not text or len(text) < MIN_POST_LENGTH:
            return

        await on_new_post(event)

    logger.info(
        "Обработчик постов зарегистрирован для %s каналов",
        len(monitored_ids),
    )


def add_monitored_channel(monitored_ids: Set[int], entity) -> None:
    """Add a channel/group to the live monitored set after joining."""
    monitored_ids.add(peer_id(entity))


def remove_monitored_channel(monitored_ids: Set[int], entity_or_id) -> bool:
    """Remove a channel from the live monitored set. Returns True if removed."""
    pid = peer_id(entity_or_id)
    if pid in monitored_ids:
        monitored_ids.discard(pid)
        return True
    return False

