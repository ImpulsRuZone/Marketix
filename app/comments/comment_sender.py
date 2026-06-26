"""
Sends a generated comment to the linked discussion group of a channel post.
Handles MsgIdInvalidError by searching for the forwarded post in the group.
"""

import logging
from uuid import UUID
from typing import Optional

from telethon import TelegramClient
from telethon.errors import MsgIdInvalidError
from telethon.tl.functions.channels import GetFullChannelRequest

from app.database import repositories as repo
from app.logs.logger import DBLogger

logger = logging.getLogger(__name__)


async def send_comment(
    client: TelegramClient,
    channel_entity,
    msg_id: int,
    comment: str,
    account_id: UUID,
    chat_db_id: Optional[UUID],
    post_db_id: Optional[UUID],
    pool,
    db_log: DBLogger,
) -> bool:
    """
    Finds the linked group and posts the comment.
    Returns True on success.
    """
    channel_name = getattr(channel_entity, "title", "?")

    # Get linked discussion group
    try:
        full = await client(GetFullChannelRequest(channel_entity))
        linked_id = full.full_chat.linked_chat_id
    except Exception as e:
        db_log.error("get_linked_group", f"[{channel_name}] Cannot get full channel: {e}")
        return False

    if not linked_id:
        db_log.warning("no_linked_group", f"[{channel_name}] No linked group, skipping")
        return False

    comment_row = await repo.create_comment(
        pool, account_id, chat_db_id, post_db_id, comment
    )

    success = await _try_send(
        client, linked_id, msg_id, comment,
        comment_row["id"], pool, db_log, channel_name,
    )
    return success


async def _try_send(
    client: TelegramClient,
    linked_id: int,
    msg_id: int,
    comment: str,
    comment_db_id: UUID,
    pool,
    db_log: DBLogger,
    label: str,
) -> bool:
    try:
        await client.send_message(
            entity=linked_id,
            message=comment,
            comment_to=msg_id,
        )
        await repo.mark_comment_sent(pool, comment_db_id, comment)
        db_log.info("comment_sent", f"[{label}] Sent: {comment[:60]}")
        return True

    except MsgIdInvalidError:
        db_log.info("searching_post", f"[{label}] MsgIdInvalid — searching in linked group")
        async for msg in client.iter_messages(linked_id, limit=20):
            if msg.fwd_from and msg.fwd_from.channel_post == msg_id:
                try:
                    await client.send_message(
                        entity=linked_id,
                        message=comment,
                        comment_to=msg.id,
                    )
                    await repo.mark_comment_sent(pool, comment_db_id, comment)
                    db_log.info("comment_sent", f"[{label}] Sent via linked id: {comment[:60]}")
                    return True
                except Exception as e:
                    await repo.mark_comment_failed(pool, comment_db_id, str(e))
                    db_log.error("send_failed", f"[{label}] {e}")
                    return False

        await repo.mark_comment_failed(pool, comment_db_id, "Post not found in linked group")
        db_log.warning("post_not_found", f"[{label}] Post not found in linked group")
        return False

    except Exception as e:
        await repo.mark_comment_failed(pool, comment_db_id, str(e))
        db_log.error("send_failed", f"[{label}] {e}")
        return False
