"""
Per-account mass-looking worker.

Flow:
  1. Join groups from masslook_groups
  2. Scan participants in each group
  3. For users with stories — view and like
"""

import asyncio
import logging
from uuid import UUID

from telethon import TelegramClient

from app.database import repositories as repo
from app.logs.logger import DBLogger
from app.masslook.group_joiner import join_masslook_groups
from app.masslook.participant_scanner import iter_users_with_stories, user_label
from app.masslook.scheduler import can_view_more
from app.masslook.story_viewer import view_and_like_stories
from app.settings.settings_manager import get_settings
from app.telegram.client_factory import create_client
from app.telegram.chat_utils import normalize_chat_url
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
            self.db_log.info("масслукинг_выключен", "masslook_enabled=false. Ожидание 60 сек")
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

        groups = await repo.get_active_masslook_groups(self.pool)
        if not groups:
            self.db_log.warning(
                "нет_групп",
                "Нет групп в masslook_groups. Ожидание 60 сек",
            )
            await self.client.disconnect()
            await asyncio.sleep(60)
            return

        await join_masslook_groups(
            self.client, self.account_id, self._settings,
            self.pool, self.db_log, account_name=self.name,
        )

        joined_groups = await repo.get_joined_masslook_groups(self.pool, self.account_id)
        if not joined_groups:
            self.db_log.warning(
                "не_в_группах",
                "Аккаунт не состоит ни в одной группе. Ожидание 60 сек",
            )
            await self.client.disconnect()
            await asyncio.sleep(60)
            return

        self.db_log.info(
            "старт_цикла",
            f"Масслукинг: {len(joined_groups)} групп для «{self.name}»",
        )

        processed = 0
        participants_limit = self._settings.get("masslook_participants_limit", 500)
        like_enabled = self._settings.get("masslook_like_enabled", True)
        reaction = self._settings.get("story_reaction_emoji", "❤️")

        for group in joined_groups:
            self._settings = await get_settings(self.pool, self.account_id)

            if not await can_view_more(self.pool, self.account_id, self._settings):
                self.db_log.info("лимит_достигнут", "Дневной лимит или окно сна")
                break

            url = normalize_chat_url(group["group_url"])
            group_title = group.get("title") or url

            try:
                entity = await self.client.get_entity(url)
            except Exception as e:
                self.db_log.warning("ошибка_группы", f"{group_title}: {e}")
                continue

            self.db_log.info("сканирование", f"Группа «{group_title}», до {participants_limit} участников")

            async for user in iter_users_with_stories(
                self.client, entity, limit=participants_limit,
            ):
                if not await can_view_more(self.pool, self.account_id, self._settings):
                    break

                label = user_label(user)
                result = await view_and_like_stories(
                    self.client, user,
                    like_enabled=like_enabled,
                    reaction_emoji=reaction,
                )

                if result.flood_wait_seconds:
                    self.db_log.warning(
                        "flood_wait",
                        f"FloodWait {result.flood_wait_seconds} сек",
                    )
                    await asyncio.sleep(result.flood_wait_seconds + 5)
                    continue

                if result.success and not result.skipped:
                    processed += 1
                    await repo.record_story_view(
                        self.pool,
                        account_id=self.account_id,
                        group_id=group["id"],
                        telegram_user_id=user.id,
                        account_name=self.name,
                        target_username=user.username,
                        target_title=label,
                        stories_count=result.stories_count,
                        liked_count=result.liked_count,
                        max_story_id=result.max_story_id,
                        status="liked" if result.liked_count else "viewed",
                    )
                    self.db_log.info(
                        "сторис_лайк",
                        f"{label}: просмотрено {result.stories_count}, "
                        f"лайков {result.liked_count}",
                    )
                elif result.skipped:
                    await repo.record_story_view(
                        self.pool,
                        account_id=self.account_id,
                        group_id=group["id"],
                        telegram_user_id=user.id,
                        account_name=self.name,
                        target_username=user.username,
                        target_title=label,
                        stories_count=0,
                        liked_count=0,
                        status="skipped",
                        error_message=result.error_message,
                    )
                else:
                    await repo.record_story_view(
                        self.pool,
                        account_id=self.account_id,
                        group_id=group["id"],
                        telegram_user_id=user.id,
                        account_name=self.name,
                        target_username=user.username,
                        target_title=label,
                        stories_count=0,
                        liked_count=0,
                        status="failed",
                        error_message=result.error_message,
                    )
                    self.db_log.warning("ошибка_сторис", f"{label}: {result.error_message}")

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
            f"Обработано пользователей: {processed}. Пауза {pause} сек",
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
