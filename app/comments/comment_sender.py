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
        db_log.error("ошибка_linked_группы", f"[{channel_name}] Не удалось получить данные канала: {e}")
        return False

    if not linked_id:
        db_log.warning("нет_linked_группы", f"[{channel_name}] Нет linked-группы, пропускаю")
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
        db_log.info("комментарий_отправлен", f"[{label}] Отправлено: {comment[:60]}")
        return True

    except MsgIdInvalidError:
        db_log.info("поиск_поста", f"[{label}] MsgIdInvalid — ищу пост в linked-группе")
        async for msg in client.iter_messages(linked_id, limit=20):
            if msg.fwd_from and msg.fwd_from.channel_post == msg_id:
                try:
                    await client.send_message(
                        entity=linked_id,
                        message=comment,
                        comment_to=msg.id,
                    )
                    await repo.mark_comment_sent(pool, comment_db_id, comment)
                    db_log.info("комментарий_отправлен", f"[{label}] Отправлено через linked id: {comment[:60]}")
                    return True
                except Exception as e:
                    await repo.mark_comment_failed(pool, comment_db_id, str(e))
                    db_log.error("ошибка_отправки", f"[{label}] {e}")
                    return False

        await repo.mark_comment_failed(pool, comment_db_id, "Пост не найден в linked-группе")
        db_log.warning("пост_не_найден", f"[{label}] Пост не найден в linked-группе")
        return False

    except Exception as e:
        await repo.mark_comment_failed(pool, comment_db_id, str(e))
        db_log.error("ошибка_отправки", f"[{label}] {e}")
        return False
