from __future__ import annotations

from telethon import TelegramClient


class CommentSender:
    async def send(self, client: TelegramClient, entity: str | int, message: str) -> int:
        sent = await client.send_message(entity=entity, message=message)
        return sent.id
