"""
Main worker for a single Telegram account.

Responsibilities:
  - Start the Telethon client
  - Check sleep window before any action
  - Check daily comment limits
  - Join chats on startup
  - Listen for new posts
  - Decide whether to comment (scheduler)
  - Generate comment (GPT)
  - Send comment
  - Write logs
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from telethon import TelegramClient

from app.database import repositories as repo
from app.logs.logger import DBLogger
from app.settings.settings_manager import get_settings
from app.telegram.client_factory import create_client
from app.telegram.join_manager import join_all_chats
from app.telegram.post_listener import register_post_handler, remove_monitored_channel
from app.telegram.chat_utils import resolve_monitored_ids, peer_id
from app.telegram.permission_errors import is_mandatory_exclusion_error
from app.comments.generator import generate_comment
from app.comments.comment_scheduler import should_comment
from app.comments.comment_sender import send_comment
from app.utils.time_utils import is_sleep_time, seconds_until_wake
from app.utils.random_utils import random_delay

logger = logging.getLogger(__name__)

# How long to sleep when inside the sleep window (check again after N seconds)
SLEEP_POLL_INTERVAL = 300  # 5 minutes


class AccountWorker:

    def __init__(self, account, pool, join_on_startup: bool = False):
        self.account = account
        self.pool = pool
        self.join_on_startup = join_on_startup
        self.account_id: UUID = account["id"]
        self.name: str = account["name"] or str(self.account_id)[:8]
        self.client: TelegramClient = create_client(account)
        self.db_log = DBLogger(
            f"worker.{self.name}",
            account_id=self.account_id,
            pool=pool,
        )
        self._settings: dict = {}
        self._chat_urls: list = []
        self._monitored_ids: set[int] = set()

    # ──────────────────────────────────────────────────────────────
    # Public entry point
    # ──────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Called by main.py. Reconnects on unexpected errors."""
        while True:
            try:
                await self._start()
            except Exception as e:
                self.db_log.error("сбой_воркера", f"Сбой: {e}. Перезапуск через 30 сек")
                await asyncio.sleep(30)

    # ──────────────────────────────────────────────────────────────
    # Startup sequence
    # ──────────────────────────────────────────────────────────────

    async def _start(self) -> None:
        self._settings = await get_settings(self.pool, self.account_id)

        if not self._settings.get("is_active", True):
            self.db_log.info("воркер_на_паузе", "Аккаунт на паузе (is_active=false). Ожидание 60 сек.")
            await asyncio.sleep(60)
            return

        self.db_log.info("запуск_воркера", "Запуск")
        await self.client.connect()

        if not await self.client.is_user_authorized():
            self.db_log.error(
                "не_авторизован",
                "Сессия недействительна. Выполните: python3 -m app.telegram.account_login",
            )
            await self.client.disconnect()
            await asyncio.sleep(300)
            return

        me = await self.client.get_me()
        self.db_log.info("авторизован", f"Вход выполнен: {me.first_name} (id={me.id})")

        # Wait if inside sleep window
        await self._wait_if_sleeping()

        # Слушаем посты сразу — не ждём окончания вступления во все каналы
        target_rows = await repo.get_joinable_target_chats(self.pool)
        self._chat_urls = [row["chat_url"] for row in target_rows if row.get("chat_url")]
        if not self._chat_urls:
            self.db_log.warning("нет_чатов", "Нет целевых чатов в target_chats. Ожидание 60 сек.")
            await self.client.disconnect()
            await asyncio.sleep(60)
            return

        self._monitored_ids = await resolve_monitored_ids(self.client, target_rows)
        register_post_handler(self.client, self._monitored_ids, self._on_new_post)

        if self.join_on_startup:
            self.db_log.info(
                "прослушивание",
                f"Слушаю {len(self._monitored_ids)}/{len(self._chat_urls)} каналов "
                f"(вступление в новые — в фоне)",
            )
            asyncio.create_task(
                join_all_chats(
                    self.client,
                    self.account_id,
                    self._settings,
                    self.pool,
                    self.db_log,
                    monitored_ids=self._monitored_ids,
                )
            )
        else:
            self.db_log.info(
                "прослушивание",
                f"Слушаю {len(self._monitored_ids)}/{len(self._chat_urls)} каналов "
                f"(вступление отключено — работаю с текущим списком)",
            )
            self.db_log.info(
                "вступление_пропущено",
                "Новые каналы не добавляются. Для вступления перезапустите с --join "
                "или JOIN_ON_STARTUP=true",
            )

        await self.client.run_until_disconnected()

    # ──────────────────────────────────────────────────────────────
    # New post handler
    # ──────────────────────────────────────────────────────────────

    async def _on_new_post(self, event) -> None:
        try:
            await self._handle_new_post(event)
        except Exception as e:
            self.db_log.error("ошибка_обработки_поста", f"Не удалось обработать пост: {e}")

    async def _handle_new_post(self, event) -> None:
        # Refresh settings each post (allows live updates without restart)
        self._settings = await get_settings(self.pool, self.account_id)

        if not self._settings.get("is_active", True):
            return

        # Check sleep window
        if is_sleep_time(
            self._settings["sleep_start_time"],
            self._settings["sleep_end_time"],
            self._settings["timezone"],
        ):
            self.db_log.info("сон", "Окно сна — пост пропущен")
            return

        # Check scheduler
        if not await should_comment(self.pool, self.account_id, self._settings):
            self.db_log.info("пост_пропущен", "Пропущен планировщиком")
            return

        channel = await event.get_chat()
        channel_name = getattr(channel, "title", "?")
        channel_username = getattr(channel, "username", "")
        post_text = event.message.text

        self._monitored_ids.add(peer_id(channel))

        # Random delay before acting (human-like behavior)
        delay = random_delay(60, 300)
        self.db_log.info(
            "новый_пост",
            f"[{channel_name}] Новый пост, ожидание {delay} сек",
            payload={"delay": delay},
        )
        await asyncio.sleep(delay)

        chat_db_id = None
        post_db_id = None
        try:
            chat_row = await repo.upsert_target_chat(
                self.pool,
                chat_url=f"@{channel_username}" if channel_username else f"id:{channel.id}",
                chat_id=channel.id,
                username=channel_username,
                title=channel_name,
            )
            chat_db_id = chat_row["id"]
            post_row = await repo.upsert_post(
                self.pool,
                chat_id=chat_db_id,
                telegram_post_id=event.message.id,
                post_text=post_text,
                post_date=event.message.date or datetime.now(timezone.utc),
            )
            post_db_id = post_row["id"]
        except Exception as e:
            self.db_log.warning(
                "ошибка_бд",
                f"[{channel_name}] Не удалось сохранить пост в БД: {e}",
            )

        try:
            comment = await generate_comment(
                post_text,
                account_prompt=self.account.get("gpt_prompt"),
            )
        except Exception as e:
            self.db_log.error("ошибка_gpt", f"Ошибка GPT: {e}")
            return

        result = await send_comment(
            client=self.client,
            channel_entity=channel,
            msg_id=event.message.id,
            comment=comment,
            account_id=self.account_id,
            chat_db_id=chat_db_id,
            post_db_id=post_db_id,
            pool=self.pool,
            db_log=self.db_log,
            post_text=post_text,
        )

        must_exclude = result.exclude_channel or (
            result.error_message and is_mandatory_exclusion_error(
                Exception(result.error_message)
            )
        )
        if must_exclude:
            await self._exclude_channel_from_monitoring(
                channel,
                channel_name,
                channel_username,
                chat_db_id,
                result.error_message or "private and you lack permission",
            )

    # ──────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────

    async def _exclude_channel_from_monitoring(
        self,
        channel,
        channel_name: str,
        channel_username: str,
        chat_db_id: Optional[UUID],
        error_message: str,
    ) -> None:
        remove_monitored_channel(self._monitored_ids, channel)

        chat_url = f"@{channel_username}" if channel_username else None
        try:
            await repo.record_channel_exclusion(
                self.pool,
                self.account_id,
                error_message,
                chat_db_id=chat_db_id,
                chat_url=chat_url,
                telegram_chat_id=channel.id,
                username=channel_username or None,
                title=channel_name,
            )
        except Exception as e:
            self.db_log.error(
                "ошибка_бд",
                f"[{channel_name}] Не удалось записать исключение канала в БД: {e}",
            )
            return

        self.db_log.warning(
            "канал_исключён",
            f"[{channel_name}] Исключён из прослушивания: {error_message}. "
            f"Осталось каналов: {len(self._monitored_ids)}",
        )

    async def _wait_if_sleeping(self) -> None:
        while is_sleep_time(
            self._settings["sleep_start_time"],
            self._settings["sleep_end_time"],
            self._settings["timezone"],
        ):
            secs = seconds_until_wake(
                self._settings["sleep_end_time"],
                self._settings["timezone"],
            )
            self.db_log.info(
                "окно_сна",
                f"Окно сна, ожидание {secs} сек до пробуждения",
            )
            await asyncio.sleep(min(secs + 60, SLEEP_POLL_INTERVAL))

    async def _get_listen_chats(self) -> list:
        """Список каналов для прослушивания — все активные target_chats."""
        rows = await repo.get_active_target_chats(self.pool)
        return [row["chat_url"] for row in rows if row.get("chat_url")]

    async def _get_chat_identifiers(self) -> list:
        """Устаревший метод — оставлен для совместимости."""
        return await self._get_listen_chats()
