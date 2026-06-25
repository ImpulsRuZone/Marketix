from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone

from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserAlreadyParticipantError
from telethon.tl.functions.channels import GetFullChannelRequest, JoinChannelRequest

from app.db.repositories import ChatRepository


class JoinManager:
    def __init__(self, chats: ChatRepository) -> None:
        self.chats = chats

    async def join_all(self, account_id: str, client: TelegramClient, min_delay: int, max_delay: int) -> None:
        account_chats = self.chats.list_account_chats(account_id)
        for index, relation in enumerate(account_chats, 1):
            chat = relation.get("target_chats")
            if not chat:
                continue
            if relation["status"] == "connected":
                continue

            label = f"[{index}/{len(account_chats)}] {chat.get('title') or chat.get('chat_url')}"
            joined = False
            try:
                entity = await client.get_entity(chat["chat_url"])
                joined = await self._join_if_needed(client, entity)

                full = await client(GetFullChannelRequest(entity))
                linked_chat_id = full.full_chat.linked_chat_id
                if linked_chat_id:
                    linked_joined = await self._join_if_needed(client, linked_chat_id)
                    joined = joined or linked_joined

                self.chats.upsert_account_chat(
                    {
                        "id": relation["id"],
                        "status": "connected",
                        "joined_at": datetime.now(timezone.utc).isoformat(),
                        "last_join_attempt_at": datetime.now(timezone.utc).isoformat(),
                        "error_message": None,
                    }
                )
            except FloodWaitError as exc:
                self.chats.upsert_account_chat(
                    {
                        "id": relation["id"],
                        "status": "failed",
                        "last_join_attempt_at": datetime.now(timezone.utc).isoformat(),
                        "error_message": f"FloodWait {exc.seconds} seconds for {label}",
                    }
                )
                await asyncio.sleep(exc.seconds + 15)
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                status = "pending" if "successfully requested to join" in message else "failed"
                self.chats.upsert_account_chat(
                    {
                        "id": relation["id"],
                        "status": status,
                        "last_join_attempt_at": datetime.now(timezone.utc).isoformat(),
                        "error_message": message,
                    }
                )
                joined = False

            if joined:
                await asyncio.sleep(random.randint(min_delay, max_delay))

    async def _join_if_needed(self, client: TelegramClient, entity) -> bool:
        try:
            await client(JoinChannelRequest(entity))
            return True
        except UserAlreadyParticipantError:
            return False
