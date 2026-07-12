"""
Per-account mass-looking worker loop.
"""

import asyncio
import logging
from uuid import UUID

from telethon import TelegramClient

from app.database import repositories as repo
from app.logs.logger import DBLogger
from app.masslook.scheduler import can_view_more
from app.masslook.story_viewer import view_stories
from app.settings.settings_manager import get_settings
from app.telegram.client_factory import create_client
from app.utils.random_utils import random_delay
from app.utils.time_utils import is_sleep_time, seconds_until_wake

logger = logging.getLogger(__name__)

SLEEP_POLL_INTERVAL = 300


class MasslookWorker:

    def __init__(self, account, pool):
        self.account = account
        self.pool = pool
        self.account_id: UUID = account["id"]
        self.name: str = account["name"] or str(self.account_id)[:8]
        self.client: TelegramClient = create_client(account)
        self.db_log = DBLogger(
            f"masslook.{self.name}",
            account_id=self.account_id,
            pool=pool,
        )
        self._settings: dict = {}

    async def run(self) -> None:
        while True:
            try:
                await self._cycle()
            except Exception as e:
                self.db_log.error("сбой_воркера", f"Сбой: {e}. Перезапуск через 30 сек")
                await asyncio.sleep(30)

    async def _cycle(self) -> None:
        self._settings = await get_settings(self.pool, self.account_id)

        if not self._settings.get("masslook_enabled", False):
            self.db_log.info(
                "масслукинг_выключен",
                "masslook_enabled=false. Ожидание 60 сек",
            )
            await asyncio.sleep(60)
            return

        if not self._settings.get("is_active", True):
            self.db_log.info("воркер_на_паузе", "Аккаунт на паузе. Ожидание 60 сек")
            await asyncio.sleep(60)
            return

        await self.client.connect()

        if not await self.client.is_user_authorized():
            self.db_log.error(
                "не_авторизован",
                "Сессия недействительна. python3 -m app.telegram.account_login",
            )
            await self.client.disconnect()
            await asyncio.sleep(300)
            return

        me = await self.client.get_me()
        self.db_log.info("авторизован", f"Вход: {me.first_name} (id={me.id})")

        targets = await repo.get_active_story_targets(self.pool)
        if not targets:
            self.db_log.warning(
                "нет_целей",
                "Нет активных целей в story_targets. Ожидание 60 сек",
            )
            await self.client.disconnect()
            await asyncio.sleep(60)
            return

        self.db_log.info(
            "старт_цикла",
            f"Масслукинг: {len(targets)} целей для аккаунта «{self.name}»",
        )

        viewed_in_cycle = 0
        for target in targets:
            self._settings = await get_settings(self.pool, self.account_id)

            if not await can_view_more(self.pool, self.account_id, self._settings):
                self.db_log.info("лимит_достигнут", "Дневной лимит или окно сна")
                break

            target_url = target["target_url"]
            target_username = target.get("username") or target_url.lstrip("@")
            target_title = target.get("title") or target_username

            result = await view_stories(self.client, target_url)

            if result.flood_wait_seconds:
                self.db_log.warning(
                    "flood_wait",
                    f"FloodWait {result.flood_wait_seconds} сек, пауза",
                )
                await asyncio.sleep(result.flood_wait_seconds + 5)
                continue

            if result.success and not result.skipped:
                viewed_in_cycle += 1
                await repo.record_story_view(
                    self.pool,
                    account_id=self.account_id,
                    target_id=target["id"],
                    account_name=self.name,
                    target_username=target_username,
                    target_title=target_title,
                    stories_count=result.stories_count,
                    max_story_id=result.max_story_id,
                    status="viewed",
                )
                self.db_log.info(
                    "сторис_просмотрены",
                    f"@{target_username}: {result.stories_count} сторис "
                    f"(max_id={result.max_story_id})",
                )
            elif result.skipped:
                await repo.record_story_view(
                    self.pool,
                    account_id=self.account_id,
                    target_id=target["id"],
                    account_name=self.name,
                    target_username=target_username,
                    target_title=target_title,
                    stories_count=0,
                    status="skipped",
                    error_message=result.error_message,
                )
            else:
                await repo.record_story_view(
                    self.pool,
                    account_id=self.account_id,
                    target_id=target["id"],
                    account_name=self.name,
                    target_username=target_username,
                    target_title=target_title,
                    stories_count=0,
                    status="failed",
                    error_message=result.error_message,
                )
                self.db_log.warning(
                    "ошибка_просмотра",
                    f"@{target_username}: {result.error_message}",
                )

            delay = random_delay(
                self._settings.get("story_view_delay_min_seconds", 5),
                self._settings.get("story_view_delay_max_seconds", 30),
            )
            await asyncio.sleep(delay)

        await self.client.disconnect()

        pause = random_delay(
            self._settings.get("masslook_cycle_pause_min_seconds", 300),
            self._settings.get("masslook_cycle_pause_max_seconds", 900),
        )
        self.db_log.info(
            "цикл_завершён",
            f"Просмотрено целей: {viewed_in_cycle}. Пауза {pause} сек",
        )

        if is_sleep_time(
            self._settings.get("sleep_start_time"),
            self._settings.get("sleep_end_time"),
            self._settings.get("timezone", "UTC"),
        ):
            secs = seconds_until_wake(
                self._settings.get("sleep_end_time"),
                self._settings.get("timezone", "UTC"),
            )
            pause = max(pause, min(secs + 60, SLEEP_POLL_INTERVAL))

        await asyncio.sleep(pause)
