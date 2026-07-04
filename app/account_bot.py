"""
Логика одного Telegram-аккаунта.
Запускается конкурентно для каждого аккаунта из accounts.json.
"""

import asyncio
import random
import logging
from typing import List, Optional

from telethon import TelegramClient, events
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.errors import MsgIdInvalidError

from app.config import AccountConfig, DELAY_MIN, DELAY_MAX
from app.ai import generate_comment
from app.joiner import join_channels
from app.channels_store import resolve_channels_for_account
from app.db import log_event, log_comment

logger = logging.getLogger(__name__)


class AccountBot:
    """Инкапсулирует один Telegram-аккаунт и его логику."""

    def __init__(self, cfg: AccountConfig, pool):
        self.cfg = cfg
        self.pool = pool
        self.channels: List[str] = []
        self.client = TelegramClient(cfg.session_path, cfg.api_id, cfg.api_hash)
        self._label = cfg.name

    # ------------------------------------------------------------------
    # Публичный интерфейс
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Авторизоваться, вступить в каналы, запустить прослушивание."""
        await log_event(self.pool, "INFO", "connecting", "Подключение...", account=self._label)

        # При первом запуске Telethon запросит код/пароль интерактивно
        await self.client.start(phone=self.cfg.phone or None)
        me = await self.client.get_me()
        logger.info(f"[{self._label}] Авторизован как {me.first_name} (id={me.id})")
        await log_event(
            self.pool, "INFO", "auth",
            f"Авторизован как {me.first_name} (id={me.id})",
            account=self._label,
        )

        self.channels = await resolve_channels_for_account(self.cfg, self.pool)
        if not self.channels:
            logger.error(
                "[%s] Список каналов пуст. Заполните лист в %s и выполните: python -m app.channels_store",
                self._label,
                "data/channels_database.xlsx",
            )
            await log_event(
                self.pool, "ERROR", "no_channels",
                "Список каналов пуст — заполните Excel-лист аккаунта",
                account=self._label,
            )
            return

        logger.info("[%s] Загружено каналов: %s", self._label, len(self.channels))
        await join_channels(self.client, self.channels, pool=self.pool, account=self._label)

        self.client.add_event_handler(
            self._handler,
            events.NewMessage(chats=self.channels),
        )
        logger.info(f"[{self._label}] Слушаю {len(self.channels)} каналов...")
        await self.client.run_until_disconnected()

    # ------------------------------------------------------------------
    # Обработчик новых сообщений
    # ------------------------------------------------------------------

    async def _handler(self, event: events.NewMessage.Event) -> None:
        if not event.message.post:
            return

        text = event.message.text
        if not text or len(text) < 50:
            return

        channel = await event.get_chat()
        channel_name = getattr(channel, "title", "Неизвестный канал")
        channel_username = getattr(channel, "username", "")
        label = f"{channel_name} (@{channel_username})" if channel_username else channel_name

        if random.random() < 0.25:
            logger.info(f"[{self._label}] [{label}] Пост пропущен (случайно)")
            await log_event(
                self.pool, "INFO", "post_skipped", "Пост пропущен случайно",
                channel_name, channel_username, account=self._label,
            )
            return

        delay = random.randint(DELAY_MIN, DELAY_MAX)
        logger.info(f"[{self._label}] [{label}] Новый пост, жду {delay} сек...")
        await log_event(
            self.pool, "INFO", "new_post", f"Новый пост, жду {delay} сек.",
            channel_name, channel_username, wait_seconds=delay, account=self._label,
        )
        await asyncio.sleep(delay)

        try:
            comment = await generate_comment(text)

            full = await self.client(GetFullChannelRequest(channel))
            linked_id = full.full_chat.linked_chat_id

            if not linked_id:
                logger.warning(f"[{self._label}] [{label}] Нет linked-группы, пропускаю")
                await log_event(
                    self.pool, "WARNING", "no_linked_group", "Нет linked-группы",
                    channel_name, channel_username, account=self._label,
                )
                return

            msg_id = event.message.id
            await self._send_comment(linked_id, msg_id, comment, label, channel_name, channel_username, text)

        except Exception as e:
            logger.error(f"[{self._label}] [{label}] Ошибка: {e}")
            await log_event(
                self.pool, "ERROR", "error", str(e),
                channel_name, channel_username, account=self._label,
            )

    async def _send_comment(
        self,
        linked_id: int,
        msg_id: int,
        comment: str,
        label: str,
        channel_name: str,
        channel_username: str,
        post_text: str,
    ) -> None:
        try:
            await self.client.send_message(
                entity=linked_id,
                message=comment,
                comment_to=msg_id,
            )
            logger.info(f"[{self._label}] [{label}] Комментарий отправлен: {comment[:60]}...")
            await log_comment(
                self.pool, channel_name, channel_username, post_text, comment,
                account=self._label,
            )

        except MsgIdInvalidError:
            logger.info(f"[{self._label}] [{label}] Ищу пост в linked-группе...")
            async for msg in self.client.iter_messages(linked_id, limit=20):
                if msg.fwd_from and msg.fwd_from.channel_post == msg_id:
                    await self.client.send_message(
                        entity=linked_id,
                        message=comment,
                        comment_to=msg.id,
                    )
                    logger.info(
                        f"[{self._label}] [{label}] Комментарий отправлен (linked): {comment[:60]}..."
                    )
                    await log_comment(
                        self.pool, channel_name, channel_username, post_text, comment,
                        account=self._label,
                    )
                    break
            else:
                logger.warning(f"[{self._label}] [{label}] Пост не найден в linked-группе")
                await log_event(
                    self.pool, "WARNING", "post_not_found",
                    "Пост не найден в linked-группе",
                    channel_name, channel_username, account=self._label,
                )
