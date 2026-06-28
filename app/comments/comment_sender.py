"""
Sends a generated comment to the linked discussion group of a channel post.
Telegram delivery is independent of the database — DB writes are best-effort.
"""

import logging
from typing import Optional, Tuple
from uuid import UUID

from telethon import TelegramClient
from telethon.errors import MsgIdInvalidError, UserAlreadyParticipantError
from telethon.tl.functions.channels import GetFullChannelRequest, JoinChannelRequest

from app.comments.send_result import CommentSendResult
from app.database import repositories as repo
from app.database.db_types import as_db_uuid
from app.logs.logger import DBLogger

logger = logging.getLogger(__name__)

_PERMISSION_ERRORS = (
    "lack permission",
    "private",
    "banned",
    "getdiscussionmessage",
    "channel_private",
    "chat_write_forbidden",
)


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
    post_text: Optional[str] = None,
) -> CommentSendResult:
    """Posts comment to Telegram. DB logging is optional and never blocks sending."""
    channel_name = getattr(channel_entity, "title", "?")

    try:
        full = await client(GetFullChannelRequest(channel_entity))
        linked_id = full.full_chat.linked_chat_id
        linked_entity = None
        if linked_id:
            linked_entity = next(
                (chat for chat in full.chats if chat.id == linked_id),
                None,
            )
    except Exception as e:
        db_log.error("ошибка_linked_группы", f"[{channel_name}] Не удалось получить данные канала: {e}")
        return CommentSendResult(False, _is_permission_error(e))

    if not linked_id:
        db_log.warning("нет_linked_группы", f"[{channel_name}] Нет linked-группы, пропускаю")
        return CommentSendResult(False, False)

    comment_db_id = await _try_save_comment_record(
        pool, account_id, chat_db_id, post_db_id, comment, post_text, db_log,
    )

    if linked_entity is not None:
        await _try_join_linked(client, linked_entity, db_log, channel_name)

    success, exclude = await _send_to_telegram(
        client, linked_id, linked_entity, msg_id, comment, db_log, channel_name,
    )

    if success:
        await _try_mark_sent(pool, comment_db_id, comment, db_log, channel_name)
    else:
        await _try_mark_failed(pool, comment_db_id, "Не удалось отправить в Telegram", db_log)

    return CommentSendResult(success, exclude)


async def _try_join_linked(client, linked_entity, db_log: DBLogger, label: str) -> None:
    try:
        await client(JoinChannelRequest(linked_entity))
        db_log.info("вступил_linked", f"[{label}] Вступил в linked-группу для комментария")
    except UserAlreadyParticipantError:
        pass
    except Exception as e:
        db_log.warning("вступление_linked", f"[{label}] Не удалось вступить в linked-группу: {e}")


async def _try_save_comment_record(
    pool,
    account_id: UUID,
    chat_db_id: Optional[UUID],
    post_db_id: Optional[UUID],
    comment: str,
    post_text: Optional[str],
    db_log: DBLogger,
):
    if pool is None:
        return None
    try:
        row = await repo.create_comment(
            pool, account_id, chat_db_id, post_db_id, comment, post_text=post_text,
        )
        return row["id"]
    except Exception as e:
        err = str(e)
        if "post_text" in err and "does not exist" in err:
            try:
                row = await repo.create_comment_legacy(
                    pool, account_id, chat_db_id, post_db_id, comment,
                )
                return row["id"]
            except Exception as e2:
                db_log.warning("ошибка_бд", f"Не удалось сохранить комментарий в БД: {e2}")
                return None
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


def _is_permission_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _PERMISSION_ERRORS)


async def _send_to_telegram(
    client: TelegramClient,
    linked_id: int,
    linked_entity,
    msg_id: int,
    comment: str,
    db_log: DBLogger,
    label: str,
) -> Tuple[bool, bool]:
    """Returns (success, exclude_channel)."""
    last_permission_error = False

    for attempt in range(2):
        try:
            await client.send_message(
                entity=linked_id,
                message=comment,
                comment_to=msg_id,
            )
            db_log.info("комментарий_отправлен", f"[{label}] Отправлено: {comment[:60]}")
            return True, False

        except MsgIdInvalidError:
            ok, exclude = await _send_via_forwarded_post(
                client, linked_id, msg_id, comment, db_log, label,
            )
            return ok, exclude

        except Exception as e:
            if _is_permission_error(e):
                last_permission_error = True
                if attempt == 0 and linked_entity is not None:
                    db_log.warning(
                        "нет_доступа_linked",
                        f"[{label}] Нет доступа к linked-группе, пробую вступить: {e}",
                    )
                    await _try_join_linked(client, linked_entity, db_log, label)
                    continue
                db_log.error("ошибка_отправки", f"[{label}] {e}")
                return False, True

            db_log.error("ошибка_отправки", f"[{label}] {e}")
            return False, False

    return False, last_permission_error


async def _send_via_forwarded_post(
    client: TelegramClient,
    linked_id: int,
    msg_id: int,
    comment: str,
    db_log: DBLogger,
    label: str,
) -> Tuple[bool, bool]:
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
                return True, False
            except Exception as e:
                db_log.error("ошибка_отправки", f"[{label}] {e}")
                return False, _is_permission_error(e)

    db_log.warning("пост_не_найден", f"[{label}] Пост не найден в linked-группе")
    return False, False
