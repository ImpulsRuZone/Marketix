"""
Registers a NewMessage event handler on the client.
Passes new channel posts to the comment pipeline.
"""

import logging
from typing import Callable, List

from telethon import TelegramClient, events

from app.config import MIN_POST_LENGTH

logger = logging.getLogger(__name__)


def register_post_handler(
    client: TelegramClient,
    chats: List[str],
    on_new_post: Callable,
) -> None:
    """
    Registers an event handler that fires for every new channel post.

    on_new_post(event) — async callback defined in account_worker.
    """

    @client.on(events.NewMessage(chats=chats))
    async def _handler(event: events.NewMessage.Event) -> None:
        if not event.message.post:
            return

        text = event.message.text
        if not text or len(text) < MIN_POST_LENGTH:
            return

        await on_new_post(event)

    logger.debug(f"Post handler registered for {len(chats)} chats")
