"""
Creates a Telethon TelegramClient from an account DB record.
Session is stored as a StringSession (saved in the DB, not on disk).
"""

from telethon import TelegramClient
from telethon.sessions import StringSession

from app.utils.proxy_utils import build_proxy


def create_client(account) -> TelegramClient:
    """
    account — asyncpg.Record or dict with keys:
        api_id, api_hash, session_string,
        proxy_enabled, proxy_type, proxy_host, proxy_port,
        proxy_username, proxy_password
    """
    session = StringSession(account["session_string"] or "")
    proxy = build_proxy(account) if account["proxy_enabled"] else None

    client = TelegramClient(
        session,
        account["api_id"],
        account["api_hash"],
        proxy=proxy,
    )
    return client
