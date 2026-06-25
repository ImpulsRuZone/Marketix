from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone

from telethon import TelegramClient

from app.db.repositories import ChatRepository


class JoinManager:
    def __init__(self, chats: ChatRepository) -> None:
        self.chats = chats

    async def join_all(self, account_id: str, client: TelegramClient, min_delay: int, max_delay: int) -> None:
        account_chats = self.chats.list_account_chats(account_id)
        for relation in account_chats:
            chat = relation.get("target_chats")
            if not chat:
                continue
            if relation["status"] == "connected":
                continue

            try:
                await client.get_entity(chat["chat_url"])
                # Joining mechanics can vary between public/private chats.
                # Keep this explicit call in one place for easier extension.
                await client(functions.channels.JoinChannelRequest(chat["chat_url"]))
                self.chats.upsert_account_chat(
                    {
                        "id": relation["id"],
                        "status": "connected",
                        "joined_at": datetime.now(timezone.utc).isoformat(),
                        "last_join_attempt_at": datetime.now(timezone.utc).isoformat(),
                        "error_message": None,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                self.chats.upsert_account_chat(
                    {
                        "id": relation["id"],
                        "status": "failed",
                        "last_join_attempt_at": datetime.now(timezone.utc).isoformat(),
                        "error_message": str(exc),
                    }
                )

            await asyncio.sleep(random.randint(min_delay, max_delay))


# Local import to keep telethon request namespace close to usage.
from telethon.tl import functions  # noqa: E402
