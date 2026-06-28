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
from uuid import UUID

from telethon import TelegramClient

from app.database import repositories as repo
from app.logs.logger import DBLogger
from app.settings.settings_manager import get_settings
from app.telegram.client_factory import create_client
from app.telegram.join_manager import join_all_chats
from app.telegram.post_listener import register_post_handler
from app.comments.generator import generate_comment
from app.comments.comment_scheduler import should_comment
from app.comments.comment_sender import send_comment
from app.utils.time_utils import is_sleep_time, seconds_until_wake
from app.utils.random_utils import random_delay

logger = logging.getLogger(__name__)

# How long to sleep when inside the sleep window (check again after N seconds)
SLEEP_POLL_INTERVAL = 300  # 5 minutes


class AccountWorker:

    def __init__(self, account, pool):
        self.account = account
        self.pool = pool
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

    # ──────────────────────────────────────────────────────────────
    # Public entry point
    # ──────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Called by main.py. Reconnects on unexpected errors."""
        while True:
            try:
                await self._start()
            except Exception as e:
                self.db_log.error("worker_crash", f"Crashed: {e}. Restarting in 30s")
                await asyncio.sleep(30)

    # ──────────────────────────────────────────────────────────────
    # Startup sequence
    # ──────────────────────────────────────────────────────────────

    async def _start(self) -> None:
        self._settings = await get_settings(self.pool, self.account_id)

        if not self._settings.get("is_active", True):
            self.db_log.info("worker_paused", "Account is paused (is_active=false). Sleeping 60s.")
            await asyncio.sleep(60)
            return

        self.db_log.info("worker_start", "Starting")
        await self.client.connect()

        if not await self.client.is_user_authorized():
            self.db_log.error(
                "not_authorized",
                "Session is invalid. Run: python -m app.telegram.account_login",
            )
            await self.client.disconnect()
            await asyncio.sleep(300)
            return

        me = await self.client.get_me()
        self.db_log.info("authorized", f"Logged in as {me.first_name} (id={me.id})")

        # Wait if inside sleep window
        await self._wait_if_sleeping()

        # Join all chats
        await join_all_chats(
            self.client, self.account_id, self._settings, self.pool, self.db_log
        )

        # Build list of chat URLs to listen to
        self._chat_urls = await self._get_chat_identifiers()
        if not self._chat_urls:
            self.db_log.warning("no_chats", "No joined chats to listen to. Sleeping 60s.")
            await self.client.disconnect()
            await asyncio.sleep(60)
            return

        # Register event handler
        register_post_handler(self.client, self._chat_urls, self._on_new_post)

        self.db_log.info("listening", f"Listening to {len(self._chat_urls)} chats")
        await self.client.run_until_disconnected()

    # ──────────────────────────────────────────────────────────────
    # New post handler
    # ──────────────────────────────────────────────────────────────

    async def _on_new_post(self, event) -> None:
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
            self.db_log.info("sleeping", "In sleep window — skipping post")
            return

        # Check scheduler
        if not await should_comment(self.pool, self.account_id, self._settings):
            self.db_log.info("post_skipped", "Skipped by scheduler")
            return

        channel = await event.get_chat()
        channel_name = getattr(channel, "title", "?")
        channel_username = getattr(channel, "username", "")
        post_text = event.message.text

        # Random delay before acting (human-like behavior)
        delay = random_delay(60, 300)
        self.db_log.info(
            "new_post",
            f"[{channel_name}] New post, waiting {delay}s",
            payload={"delay": delay},
        )
        await asyncio.sleep(delay)

        # Save post to DB
        chat_row = await repo.upsert_target_chat(
            self.pool,
            chat_url=f"@{channel_username}" if channel_username else f"id:{channel.id}",
            chat_id=channel.id,
            username=channel_username,
            title=channel_name,
        )

        post_row = await repo.upsert_post(
            self.pool,
            chat_id=chat_row["id"],
            telegram_post_id=event.message.id,
            post_text=post_text,
            post_date=event.message.date or datetime.now(timezone.utc),
        )

        # Generate comment
        try:
            comment = await generate_comment(
                post_text,
                account_prompt=self.account.get("gpt_prompt"),
            )
        except Exception as e:
            self.db_log.error("gpt_error", f"GPT error: {e}")
            return

        # Send comment
        await send_comment(
            client=self.client,
            channel_entity=channel,
            msg_id=event.message.id,
            comment=comment,
            account_id=self.account_id,
            chat_db_id=chat_row["id"],
            post_db_id=post_row["id"],
            pool=self.pool,
            db_log=self.db_log,
        )

    # ──────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────

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
                "sleep_window",
                f"In sleep window, waiting {secs}s until wake",
            )
            await asyncio.sleep(min(secs + 60, SLEEP_POLL_INTERVAL))

    async def _get_chat_identifiers(self) -> list:
        """Returns list of chat usernames/ids for event handler registration."""
        rows = await repo.get_account_chats(self.pool, self.account_id)
        result = []
        for row in rows:
            if row["status"] in ("joined", "requested"):
                url = row["chat_url"]
                if url:
                    result.append(url)
        return result
