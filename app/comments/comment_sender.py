"""
Sends a generated comment to the linked discussion group of a channel post.
Telegram delivery is independent of the database — DB writes are best-effort.
"""

import logging
from typing import Optional
from uuid import UUID

from telethon import TelegramClient
from telethon.errors import MsgIdInvalidError
from telethon.tl.functions.channels import GetFullChannelRequest

from app.database import repositories as repo
from app.database.db_types import as_db_uuid
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
    """Posts comment to Telegram. DB logging is optional and never blocks sending."""
    channel_name = getattr(channel_entity, "title", "?")

    try:
        full = await client(GetFullChannelRequest(channel_entity))
        linked_id = full.full_chat.linked_chat_id
    except Exception as e:
        db_log.error("ошибка_linked_группы", f"[{channel_name}] Не удалось получить данные канала: {e}")
        return False

    if not linked_id:
        db_log.warning("нет_linked_группы", f"[{channel_name}] Нет linked-группы, пропускаю")
        return False

    comment_db_id = await _try_save_comment_record(
        pool, account_id, chat_db_id, post_db_id, comment, db_log,
    )

    success = await _send_to_telegram(
        client, linked_id, msg_id, comment, db_log, channel_name,
    )

    if success:
        await _try_mark_sent(pool, comment_db_id, comment, db_log, channel_name)
    else:
        await _try_mark_failed(pool, comment_db_id, "Не удалось отправить в Telegram", db_log)

    return success


async def _try_save_comment_record(
    pool,
    account_id: UUID,
    chat_db_id: Optional[UUID],
    post_db_id: Optional[UUID],
    comment: str,
    db_log: DBLogger,
):
    if pool is None:
        return None
    try:
        row = await repo.create_comment(
            pool, account_id, chat_db_id, post_db_id, comment,
        )
        return row["id"]
    except Exception as e:
        db_log.warning("ошибка_бд", f"Не удалось сохранить комментарий в БД: {e}")
        return None


async def _try_mark_sent(pool, comment_db_id, comment: str, db_log: DBLogger, label: str) -> None:
    if pool is None or comment_db_id is None:
        return
    try:
        await repo.mark_comment_sent(pool, as_db_uuid(comment_db_id), comment)
    except Exception as e:
        db_log.warning("ошибка_бд", f"[{label}] Комментарий отправлен, но не сохранён в БД: {e}")


async def _try_mark_failed(pool, comment_db_id, error_message: str, db_log: DBLogger) -> None:
    if pool is None or comment_db_id is None:
        return
    try:
        await repo.mark_comment_failed(pool, as_db_uuid(comment_db_id), error_message)
    except Exception as e:
        db_log.warning("ошибка_бд", f"Не удалось записать ошибку комментария в БД: {e}")


async def _send_to_telegram(
    client: TelegramClient,
    linked_id: int,
    msg_id: int,
    comment: str,
    db_log: DBLogger,
    label: str,
) -> bool:
    try:
        await client.send_message(
            entity=linked_id,
            message=comment,
            comment_to=msg_id,
        )
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
                    db_log.info(
                        "комментарий_отправлен",
                        f"[{label}] Отправлено через linked id: {comment[:60]}",
                    )
                    return True
                except Exception as e:
                    db_log.error("ошибка_отправки", f"[{label}] {e}")
                    return False

        db_log.warning("пост_не_найден", f"[{label}] Пост не найден в linked-группе")
        return False

    except Exception as e:
        db_log.error("ошибка_отправки", f"[{label}] {e}")
        return False
