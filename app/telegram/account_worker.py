from __future__ import annotations

import asyncio
import random
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from telethon import TelegramClient, events
from telethon.errors import MsgIdInvalidError
from telethon.tl.functions.channels import GetFullChannelRequest

from app.comments.generator import CommentGenerator
from app.config import settings as global_settings
from app.db.repositories import ChatRepository, CommentRepository
from app.logs.logger import AccountLogger
from app.telegram.client_factory import build_client
from app.telegram.join_manager import JoinManager


class AccountWorker:
    def __init__(
        self,
        account: dict,
        account_settings: dict,
        chats: ChatRepository,
        comments: CommentRepository,
        logger: AccountLogger,
        generator: CommentGenerator,
        join_manager: JoinManager,
    ) -> None:
        self.account = account
        self.settings = account_settings
        self.chats = chats
        self.comments = comments
        self.logger = logger
        self.generator = generator
        self.join_manager = join_manager
        self.client: TelegramClient = build_client(account)

    async def run(self) -> None:
        await self.client.start()
        self.logger.info(self.account["id"], "worker_started", "Аккаунт подключен к Telegram")

        await self.join_manager.join_all(
            account_id=self.account["id"],
            client=self.client,
            min_delay=int(self.settings.get("join_delay_min_seconds", 60)),
            max_delay=int(self.settings.get("join_delay_max_seconds", 180)),
        )
        watch_chats = await self._resolve_watch_chats()
        if not watch_chats:
            self.logger.warning(self.account["id"], "no_target_chats", "Нет доступных целевых каналов")
            return

        @self.client.on(events.NewMessage(chats=watch_chats))
        async def on_new_message(event: events.NewMessage.Event) -> None:
            await self._handle_channel_post(event)

        await self.client.run_until_disconnected()

    async def _resolve_watch_chats(self) -> list:
        watch: list = []
        account_chats = self.chats.list_account_chats(self.account["id"])
        for relation in account_chats:
            chat = relation.get("target_chats")
            if not chat:
                continue
            if relation["status"] == "disabled" or not chat.get("is_active"):
                continue
            entity_ref = chat.get("chat_url") or chat.get("chat_id")
            if not entity_ref:
                continue
            try:
                entity = await self.client.get_entity(entity_ref)
                watch.append(entity)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(
                    self.account["id"],
                    "target_chat_unresolved",
                    "Не удалось получить целевой чат",
                    {"entity": entity_ref, "error": str(exc)},
                )
        return watch

    async def _handle_channel_post(self, event: events.NewMessage.Event) -> None:
        if not event.message.post:
            return

        post_text = event.message.text or event.message.message or ""
        if len(post_text.strip()) < 50:
            return

        channel = await event.get_chat()
        channel_name = getattr(channel, "title", "Неизвестный канал")
        channel_username = getattr(channel, "username", "")
        label = f"{channel_name} (@{channel_username})" if channel_username else channel_name

        if self._is_sleep_time():
            self.logger.info(
                self.account["id"],
                "sleep_window",
                "Пропуск в окно сна",
                {"channel": label, "post_id": event.message.id},
            )
            return

        if not self._is_within_daily_limits():
            self.logger.warning(self.account["id"], "daily_limit_reached", "Достигнут дневной лимит комментариев")
            return

        if random.randint(1, 100) > int(self.settings["daily_comment_percent"]):
            self.logger.info(
                self.account["id"],
                "post_skipped",
                "Пост пропущен по проценту комментирования",
                {"channel": label, "post_id": event.message.id},
            )
            return

        delay_seconds = random.randint(
            int(self.settings.get("comment_delay_min_seconds", global_settings.comment_delay_min_seconds)),
            int(self.settings.get("comment_delay_max_seconds", global_settings.comment_delay_max_seconds)),
        )
        self.logger.info(
            self.account["id"],
            "new_post",
            "Новый пост, ожидание перед комментарием",
            {"channel": label, "post_id": event.message.id, "delay_seconds": delay_seconds},
        )
        await asyncio.sleep(delay_seconds)

        generated_comment = self.generator.generate(post_text, self.account["gpt_prompt"])
        comment_row = self.comments.create_comment(
            {
                "account_id": self.account["id"],
                "chat_id": str(event.chat_id),
                "post_id": str(event.message.id),
                "post_text": post_text,
                "generated_comment": generated_comment,
                "status": "generated",
            }
        )

        try:
            sent_message_id = await self._send_comment_to_linked(event, channel, generated_comment)
            self.comments.update_comment_status(
                comment_id=comment_row["id"],
                status="sent",
                sent_comment=generated_comment,
            )
            self.logger.info(
                self.account["id"],
                "comment_sent",
                "Комментарий отправлен",
                {"channel": label, "post_id": event.message.id, "message_id": sent_message_id},
            )
        except Exception as exc:  # noqa: BLE001
            self.comments.update_comment_status(comment_row["id"], "failed", error_message=str(exc))
            self.logger.error(
                self.account["id"],
                "comment_failed",
                "Ошибка отправки комментария",
                {"channel": label, "post_id": event.message.id, "error": str(exc)},
            )

    def _parse_time(self, value: str) -> time:
        try:
            return datetime.strptime(value, "%H:%M:%S").time()
        except ValueError:
            return datetime.strptime(value, "%H:%M").time()

    def _is_sleep_time(self) -> bool:
        timezone_name = self.settings.get("timezone") or global_settings.default_timezone
        now_local = datetime.now(ZoneInfo(timezone_name))
        sleep_start = self._parse_time(self.settings["sleep_start_time"])
        sleep_end = self._parse_time(self.settings["sleep_end_time"])
        if sleep_start < sleep_end:
            return sleep_start <= now_local.time() < sleep_end
        return now_local.time() >= sleep_start or now_local.time() < sleep_end

    def _is_within_daily_limits(self) -> bool:
        timezone_name = self.settings.get("timezone") or global_settings.default_timezone
        now_local = datetime.now(ZoneInfo(timezone_name))
        day_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        day_start_iso = day_start_local.astimezone(timezone.utc).isoformat()
        today_sent = self.comments.count_today_sent_comments(self.account["id"], day_start_iso)
        return today_sent < int(self.settings["max_comments_per_day"])

    async def _send_comment_to_linked(self, event: events.NewMessage.Event, channel: object, comment: str) -> int:
        full = await self.client(GetFullChannelRequest(channel))
        linked_chat_id = full.full_chat.linked_chat_id
        if not linked_chat_id:
            raise RuntimeError("У канала нет linked-группы для комментариев")

        post_id = event.message.id
        try:
            sent = await self.client.send_message(
                entity=linked_chat_id,
                message=comment,
                comment_to=post_id,
            )
            return sent.id
        except MsgIdInvalidError:
            async for msg in self.client.iter_messages(linked_chat_id, limit=20):
                if msg.fwd_from and msg.fwd_from.channel_post == post_id:
                    sent = await self.client.send_message(
                        entity=linked_chat_id,
                        message=comment,
                        comment_to=msg.id,
                    )
                    return sent.id
        raise RuntimeError("Не удалось сопоставить пост в linked-группе")
