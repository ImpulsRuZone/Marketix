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
from typing import List
from uuid import UUID

from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserAlreadyParticipantError
from telethon.tl.functions.channels import JoinChannelRequest, GetFullChannelRequest

from app.database import repositories as repo
from app.logs.logger import DBLogger
from app.utils.random_utils import random_delay

logger = logging.getLogger(__name__)


async def join_all_chats(
    client: TelegramClient,
    account_id: UUID,
    settings: dict,
    pool,
    db_log: DBLogger,
) -> None:
    """Entry point called by account_worker on startup."""
    target_chats = await repo.get_active_target_chats(pool)
    if not target_chats:
        db_log.info("join_manager", "No active target chats found")
        return

    joined_chats = {
        str(row["chat_id"]): row["status"]
        for row in await repo.get_account_chats(pool, account_id)
    }

    db_log.info("join_manager", f"Checking {len(target_chats)} chats to join")

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
        )

        if did_join:
            delay = random_delay(
                settings["join_delay_min_seconds"],
                settings["join_delay_max_seconds"],
            )
            db_log.info("join_manager", f"Waiting {delay}s before next join")
            await asyncio.sleep(delay)


async def _join_one(
    client: TelegramClient,
    account_id: UUID,
    chat_row,
    pool,
    db_log: DBLogger,
    delay_min: int,
    delay_max: int,
) -> bool:
    """Joins one chat + its linked group. Returns True if any join happened."""
    url = chat_row["chat_url"]
    chat_db_id = chat_row["id"]

    try:
        entity = await client.get_entity(url)
    except Exception as e:
        db_log.error("join_error", f"Cannot resolve entity {url}: {e}")
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

    # Join linked discussion group
    try:
        full = await client(GetFullChannelRequest(entity))
        linked_id = full.full_chat.linked_chat_id
        if linked_id:
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
                f"linked group '{linked_title}'",
                account_id, linked_chat["id"], pool, db_log,
            )
            joined = joined or linked_joined
    except Exception:
        pass

    return joined


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
        db_log.info("joined", f"Joined: {label}")
        await repo.upsert_account_chat(
            pool, account_id, chat_db_id, "joined",
            joined_at=datetime.now(timezone.utc),
        )
        return True

    except UserAlreadyParticipantError:
        db_log.info("already_joined", f"Already in: {label}")
        await repo.upsert_account_chat(
            pool, account_id, chat_db_id, "joined",
            joined_at=datetime.now(timezone.utc),
        )
        return False

    except FloodWaitError as e:
        db_log.warning("flood_wait", f"FloodWait {e.seconds}s for {label}")
        await asyncio.sleep(e.seconds + 15)
        await repo.upsert_account_chat(pool, account_id, chat_db_id, "pending")
        return False

    except Exception as e:
        if "successfully requested to join" in str(e):
            db_log.info("join_requested", f"Join request sent: {label}")
            await repo.upsert_account_chat(pool, account_id, chat_db_id, "requested")
            return False
        db_log.error("join_error", f"Error joining {label}: {e}")
        await repo.upsert_account_chat(pool, account_id, chat_db_id, "failed", str(e))
        return False
