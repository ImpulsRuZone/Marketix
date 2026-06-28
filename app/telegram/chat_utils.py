"""Helpers for resolving and matching Telegram chat identifiers."""

from typing import Iterable, Set, Union

from telethon import utils
from telethon.tl.types import Channel, Chat, PeerChannel


def peer_id(entity_or_id: Union[object, int]) -> int:
    """Normalize any channel/chat entity or id to Telethon peer id."""
    if isinstance(entity_or_id, int):
        if entity_or_id > 0:
            return utils.get_peer_id(PeerChannel(entity_or_id))
        return entity_or_id
    return utils.get_peer_id(entity_or_id)


def normalize_chat_url(url: str) -> str:
    """@username from t.me links and bare usernames."""
    url = (url or "").strip()
    if not url:
        return url
    if url.startswith("https://t.me/"):
        url = url.rstrip("/").split("/")[-1]
    if url.startswith("@"):
        return url
    if url.startswith("id:"):
        return url
    return f"@{url}"


async def resolve_monitored_ids(client, target_rows: Iterable) -> Set[int]:
    """
    Build a set of peer ids for active target chats.
    Uses stored chat_id when available, otherwise resolves chat_url.
    """
    monitored: Set[int] = set()

    for row in target_rows:
        stored_id = row.get("chat_id")
        if stored_id is not None and str(stored_id).lstrip("-").isdigit():
            monitored.add(peer_id(int(stored_id)))
            continue

        chat_url = row.get("chat_url")
        if not chat_url or str(chat_url).startswith("id:"):
            continue

        try:
            entity = await client.get_entity(normalize_chat_url(chat_url))
            if isinstance(entity, (Channel, Chat)):
                monitored.add(peer_id(entity))
        except Exception:
            continue

    return monitored
