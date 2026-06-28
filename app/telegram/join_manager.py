"""
Handles joining target chats for one account.

Logic:
  1. Load active target_chats from DB
  2. For each chat not yet joined (or in 'pending' state):
     a. Attempt to join the main channel
     b. If the channel has a linked discussion group — join that too
     c. Record result in account_chats
     d. Random delay between joins (from account settings)
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional, Set
from uuid import UUID

from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserAlreadyParticipantError
from telethon.tl.functions.channels import JoinChannelRequest, GetFullChannelRequest

from app.database import repositories as repo
from app.logs.logger import DBLogger
from app.telegram.chat_utils import normalize_chat_url
from app.telegram.post_listener import add_monitored_channel
from app.utils.random_utils import random_delay

logger = logging.getLogger(__name__)


async def join_all_chats(
    client: TelegramClient,
    account_id: UUID,
    settings: dict,
    pool,
    db_log: DBLogger,
    monitored_ids: Optional[Set[int]] = None,
) -> None:
    """Entry point called by account_worker on startup."""
    target_chats = await repo.get_active_target_chats(pool)
    if not target_chats:
        db_log.info("менеджер_вступлений", "Активные целевые чаты не найдены")
        return

    joined_chats = {
        str(row["chat_id"]): row["status"]
        for row in await repo.get_account_chats(pool, account_id)
    }

    db_log.info("менеджер_вступлений", f"Проверяю {len(target_chats)} чатов для вступления")

    for chat in target_chats:
        chat_db_id = str(chat["id"])
        current_status = joined_chats.get(chat_db_id)

        if current_status == "joined":
            continue

        url = chat["chat_url"]
        did_join = await _join_one(
            client, account_id, chat, pool, db_log,
            settings["join_delay_min_seconds"],
            settings["join_delay_max_seconds"],
            monitored_ids=monitored_ids,
        )

        if did_join:
            delay = random_delay(
                settings["join_delay_min_seconds"],
                settings["join_delay_max_seconds"],
            )
            db_log.info("менеджер_вступлений", f"Ожидание {delay} сек перед следующим вступлением")
            await asyncio.sleep(delay)


async def _join_one(
    client: TelegramClient,
    account_id: UUID,
    chat_row,
    pool,
    db_log: DBLogger,
    delay_min: int,
    delay_max: int,
    monitored_ids: Optional[Set[int]] = None,
) -> bool:
    """Joins one chat + its linked group. Returns True if any join happened."""
    url = normalize_chat_url(chat_row["chat_url"])
    chat_db_id = chat_row["id"]

    try:
        entity = await client.get_entity(url)
    except Exception as e:
        db_log.error("ошибка_вступления", f"Не удалось найти канал {url}: {e}")
        await repo.upsert_account_chat(pool, account_id, chat_db_id, "failed", str(e))
        return False

    title = getattr(entity, "title", url)
    username = getattr(entity, "username", "")

    # Update chat metadata in target_chats
    await repo.upsert_target_chat(
        pool,
        chat_url=url,
        chat_id=entity.id,
        username=username,
        title=title,
        chat_type="channel" if hasattr(entity, "broadcast") else "group",
    )

    joined = await _try_join(client, entity, f"{title} ({url})", account_id, chat_db_id, pool, db_log)
    if monitored_ids is not None:
        add_monitored_channel(monitored_ids, entity)

    # Join linked discussion group
    try:
        full = await client(GetFullChannelRequest(entity))
        linked_id = full.full_chat.linked_chat_id
        if linked_id:
            linked_entity = next(
                (chat for chat in full.chats if chat.id == linked_id),
                None,
            )
            if linked_entity is None:
                linked_entity = await client.get_entity(linked_id)
            linked_title = getattr(linked_entity, "title", str(linked_id))
            linked_chat = await repo.upsert_target_chat(
                pool,
                chat_url=f"id:{linked_id}",
                chat_id=linked_id,
                title=linked_title,
                chat_type="group",
            )
            linked_joined = await _try_join(
                client, linked_entity,
                f"linked-группа «{linked_title}»",
                account_id, linked_chat["id"], pool, db_log,
            )
            joined = joined or linked_joined
    except Exception:
        pass

    return joined


async def _save_join_status(
    pool, account_id, chat_db_id, status, db_log, label,
    error_message=None, joined_at=None,
) -> None:
    try:
        await repo.upsert_account_chat(
            pool, account_id, chat_db_id, status,
            error_message=error_message, joined_at=joined_at,
        )
    except Exception as e:
        db_log.error(
            "ошибка_сохранения_бд",
            f"В Telegram всё ОК для {label}, но не удалось сохранить в БД: {e}",
        )


async def _try_join(
    client: TelegramClient,
    entity,
    label: str,
    account_id: UUID,
    chat_db_id: UUID,
    pool,
    db_log: DBLogger,
) -> bool:
    try:
        await client(JoinChannelRequest(entity))
        db_log.info("вступил", f"Вступил: {label}")
        await _save_join_status(
            pool, account_id, chat_db_id, "joined", db_log, label,
            joined_at=datetime.now(timezone.utc),
        )
        return True

    except UserAlreadyParticipantError:
        db_log.info("уже_в_канале", f"Уже состоит: {label}")
        await _save_join_status(
            pool, account_id, chat_db_id, "joined", db_log, label,
            joined_at=datetime.now(timezone.utc),
        )
        return False

    except FloodWaitError as e:
        db_log.warning("флудвейт", f"FloodWait {e.seconds} сек для {label}")
        await asyncio.sleep(e.seconds + 15)
        await _save_join_status(pool, account_id, chat_db_id, "pending", db_log, label)
        return False

    except Exception as e:
        if "successfully requested to join" in str(e):
            db_log.info("заявка_отправлена", f"Заявка на вступление отправлена: {label}")
            await _save_join_status(pool, account_id, chat_db_id, "requested", db_log, label)
            return False
        db_log.error("ошибка_вступления", f"Ошибка вступления в {label}: {e}")
        await _save_join_status(
            pool, account_id, chat_db_id, "failed", db_log, label, error_message=str(e),
        )
        return False
