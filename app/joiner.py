import asyncio
import random
import logging
from typing import List, Optional

from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest, GetFullChannelRequest
from telethon.errors import FloodWaitError, UserAlreadyParticipantError

from app.config import JOIN_DELAY_MIN, JOIN_DELAY_MAX

logger = logging.getLogger(__name__)

# Глобальный список каналов — используется если у аккаунта нет своего списка
MY_CHANNELS: List[str] = [
    "@moscow",
    "@rozetked",
    "@memachh",
    "@okx_ru",
    "@vottakkanalMoskva1",
    "@MinskMira",
    "stambul_chat2",
    "n8node_edu",
    "@nexta_live",
    "@shot_shot",
    "@ru2ch",
    "@bomber_fighter",
    "@lentachold",
    "@moscowes",
    "@live_piter",
    "@milinfolive",
    "@chp_crimea",
    "@petrovtel",
    "@kazancity",
    "@mashmoyka",
    "@kosti",
    "@oldlentach",
    "@moscowplus",
    "@spbtoday",
    "@kazan_bass",
]


async def _get_channel_name(client: TelegramClient, entity) -> str:
    try:
        full_entity = await client.get_entity(entity)
        return getattr(full_entity, "title", str(entity))
    except Exception:
        return str(entity)


async def _join_if_needed(
    client: TelegramClient,
    entity,
    label: str,
    pool=None,
    account: str = "",
) -> bool:
    from app.db import log_event

    try:
        await client(JoinChannelRequest(entity))
        logger.info(f"[{account}] Вступил в: {label}")
        if pool:
            await log_event(pool, "INFO", "joined", f"Вступил в: {label}", account=account)
        return True
    except UserAlreadyParticipantError:
        logger.info(f"[{account}] Уже в канале: {label}")
        return False
    except FloodWaitError as e:
        logger.warning(f"[{account}] FloodWait, жду {e.seconds} сек...")
        if pool:
            await log_event(
                pool, "WARNING", "flood_wait",
                f"FloodWait {e.seconds} сек.",
                wait_seconds=e.seconds,
                account=account,
            )
        await asyncio.sleep(e.seconds + 15)
        return False
    except Exception as e:
        if "successfully requested to join" in str(e):
            logger.info(f"[{account}] Заявка отправлена (закрытый канал): {label}")
            return False
        logger.error(f"[{account}] Ошибка при вступлении в {label}: {e}")
        if pool:
            await log_event(pool, "ERROR", "join_error", str(e), account=account)
        return False


async def join_channels(
    client: TelegramClient,
    channels: List[str],
    pool=None,
    account: str = "",
) -> None:
    from app.db import log_event

    logger.info(f"[{account}] Всего каналов: {len(channels)}")
    if pool:
        await log_event(
            pool, "INFO", "channels_total",
            f"Всего каналов: {len(channels)}",
            account=account,
        )

    for i, username in enumerate(channels, 1):
        try:
            entity = await client.get_entity(username)
            channel_name = getattr(entity, "title", username)

            joined = await _join_if_needed(
                client, entity,
                f"[{i}/{len(channels)}] {channel_name} ({username})",
                pool=pool,
                account=account,
            )

            full = await client(GetFullChannelRequest(entity))
            if full.full_chat.linked_chat_id:
                linked_id = full.full_chat.linked_chat_id
                linked_name = await _get_channel_name(client, linked_id)
                linked_joined = await _join_if_needed(
                    client,
                    linked_id,
                    f"linked-группа '{linked_name}' канала {username}",
                    pool=pool,
                    account=account,
                )
                joined = joined or linked_joined
            else:
                logger.info(f"[{account}] У канала {channel_name} нет linked-группы")

        except Exception as e:
            logger.error(f"[{account}] Ошибка {username}: {e}")
            if pool:
                await log_event(pool, "ERROR", "join_error", str(e), username, account=account)
            continue

        if joined:
            delay = random.randint(JOIN_DELAY_MIN, JOIN_DELAY_MAX)
            logger.info(f"[{account}] Жду {delay} сек...")
            await asyncio.sleep(delay)

    logger.info(f"[{account}] Вступление во все каналы завершено")
