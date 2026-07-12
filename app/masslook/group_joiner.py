"""
Join masslook_groups for one account.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserAlreadyParticipantError
from telethon.tl.functions.channels import JoinChannelRequest

from app.database import repositories as repo
from app.logs.logger import DBLogger
from app.telegram.chat_utils import normalize_chat_url
from app.utils.random_utils import random_delay

logger = logging.getLogger(__name__)


async def join_masslook_groups(
    client: TelegramClient,
    account_id: UUID,
    settings: dict,
    pool,
    db_log: DBLogger,
    account_name: Optional[str] = None,
) -> int:
    """Join all active masslook_groups. Returns count of new joins."""
    groups = await repo.get_active_masslook_groups(pool)
    if not groups:
        db_log.warning("нет_групп", "Нет активных групп в masslook_groups")
        return 0

    joined_rows = await repo.get_masslook_account_groups(pool, account_id)
    status_map = {str(r["group_id"]): r["status"] for r in joined_rows}

    db_log.info("вступление_в_группы", f"Проверяю {len(groups)} групп")
    new_joins = 0

    for group in groups:
        group_db_id = str(group["id"])
        if status_map.get(group_db_id) == "joined":
            continue

        did_join = await _join_one_group(
            client, account_id, group, pool, db_log, account_name=account_name,
        )
        if did_join:
            new_joins += 1
            delay = random_delay(
                settings.get("join_delay_min_seconds", 120),
                settings.get("join_delay_max_seconds", 600),
            )
            db_log.info("пауза_вступления", f"Ожидание {delay} сек перед следующей группой")
            await asyncio.sleep(delay)

    return new_joins


async def _join_one_group(
    client: TelegramClient,
    account_id: UUID,
    group_row,
    pool,
    db_log: DBLogger,
    account_name: Optional[str] = None,
) -> bool:
    url = normalize_chat_url(group_row["group_url"])
    group_db_id = group_row["id"]

    try:
        entity = await client.get_entity(url)
    except Exception as e:
        db_log.error("ошибка_группы", f"Не найдена группа {url}: {e}")
        await repo.upsert_masslook_account_group(
            pool, account_id, group_db_id, "failed",
            error_message=str(e), account_name=account_name,
            group_title=group_row.get("title"),
        )
        return False

    title = getattr(entity, "title", url)
    username = getattr(entity, "username", "")

    await repo.upsert_masslook_group(
        pool, group_url=url, telegram_id=entity.id,
        username=username, title=title,
    )

    try:
        await client(JoinChannelRequest(entity))
        db_log.info("вступил_в_группу", f"Вступил: {title} ({url})")
        await repo.upsert_masslook_account_group(
            pool, account_id, group_db_id, "joined",
            joined_at=datetime.now(timezone.utc),
            account_name=account_name, group_title=title,
        )
        return True

    except UserAlreadyParticipantError:
        db_log.info("уже_в_группе", f"Уже состоит: {title}")
        await repo.upsert_masslook_account_group(
            pool, account_id, group_db_id, "joined",
            joined_at=datetime.now(timezone.utc),
            account_name=account_name, group_title=title,
        )
        return False

    except FloodWaitError as e:
        db_log.warning("flood_wait", f"FloodWait {e.seconds} сек для {title}")
        await asyncio.sleep(e.seconds + 15)
        await repo.upsert_masslook_account_group(
            pool, account_id, group_db_id, "pending",
            account_name=account_name, group_title=title,
        )
        return False

    except Exception as e:
        if "successfully requested to join" in str(e):
            db_log.info("заявка_на_группу", f"Заявка отправлена: {title}")
            await repo.upsert_masslook_account_group(
                pool, account_id, group_db_id, "requested",
                account_name=account_name, group_title=title,
            )
            return False
        db_log.error("ошибка_вступления", f"Ошибка вступления в {title}: {e}")
        await repo.upsert_masslook_account_group(
            pool, account_id, group_db_id, "failed",
            error_message=str(e), account_name=account_name, group_title=title,
        )
        return False
