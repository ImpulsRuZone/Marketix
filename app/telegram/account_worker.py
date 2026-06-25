from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from telethon import TelegramClient, events

from app.comments.comment_scheduler import CommentScheduler
from app.comments.generator import CommentGenerator
from app.config import settings as global_settings
from app.db.repositories import CommentRepository
from app.logs.logger import AccountLogger
from app.telegram.client_factory import build_client


class AccountWorker:
    def __init__(
        self,
        account: dict,
        account_settings: dict,
        comments: CommentRepository,
        logger: AccountLogger,
        generator: CommentGenerator,
    ) -> None:
        self.account = account
        self.settings = account_settings
        self.comments = comments
        self.logger = logger
        self.generator = generator
        self.client: TelegramClient = build_client(account)

    async def run(self) -> None:
        await self.client.start()
        self.logger.info(self.account["id"], "worker_started", "Account worker started")

        @self.client.on(events.NewMessage(incoming=True))
        async def on_new_message(event: events.NewMessage.Event) -> None:
            if not event.message.message:
                return
            if event.is_private:
                return
            await self._handle_post(event.chat_id, event.message.id, event.message.message)

        await self.client.run_until_disconnected()

    async def _handle_post(self, chat_id: int | None, post_id: int, post_text: str) -> None:
        if chat_id is None:
            return

        timezone_name = self.settings.get("timezone") or global_settings.default_timezone
        now_local = datetime.now(ZoneInfo(timezone_name))
        sleep_start = datetime.strptime(self.settings["sleep_start_time"], "%H:%M:%S").time()
        sleep_end = datetime.strptime(self.settings["sleep_end_time"], "%H:%M:%S").time()
        if CommentScheduler.is_sleep_time(timezone_name, sleep_start, sleep_end):
            self.logger.info(self.account["id"], "sleep_window", "Skipped post due to sleep window")
            return

        if not CommentScheduler.should_comment(random.randint(1, 100), self.settings["daily_comment_percent"]):
            return

        day_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        day_start_iso = day_start_local.astimezone(timezone.utc).isoformat()
        today_sent = self.comments.count_today_sent_comments(self.account["id"], day_start_iso)
        if today_sent >= self.settings["max_comments_per_day"]:
            self.logger.warning(self.account["id"], "daily_limit_reached", "Daily comment limit reached")
            return

        generated_comment = self.generator.generate(post_text, self.account["gpt_prompt"])
        comment_row = self.comments.create_comment(
            {
                "account_id": self.account["id"],
                "chat_id": str(chat_id),
                "post_id": str(post_id),
                "post_text": post_text,
                "generated_comment": generated_comment,
                "status": "generated",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        delay_seconds = CommentScheduler.resolve_delay(
            self.settings.get("comment_delay_min_seconds", global_settings.comment_delay_min_seconds),
            self.settings.get("comment_delay_max_seconds", global_settings.comment_delay_max_seconds),
        )
        await asyncio.sleep(delay_seconds)

        try:
            sent = await self.client.send_message(entity=chat_id, message=generated_comment, reply_to=post_id)
            self.comments.update_comment_status(
                comment_id=comment_row["id"],
                status="sent",
                sent_comment=generated_comment,
            )
            self.logger.info(
                self.account["id"],
                "comment_sent",
                "Comment sent",
                {"chat_id": chat_id, "post_id": post_id, "message_id": sent.id},
            )
        except Exception as exc:  # noqa: BLE001
            self.comments.update_comment_status(comment_row["id"], "failed", error_message=str(exc))
            self.logger.error(self.account["id"], "comment_failed", "Failed to send comment", {"error": str(exc)})
