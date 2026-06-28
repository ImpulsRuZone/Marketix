"""
Creates a Telethon TelegramClient from an account DB record.
Session is stored as a StringSession (saved in the DB, not on disk).
API credentials are global — from .env (API_ID, API_HASH).
"""

from telethon import TelegramClient
from telethon.sessions import StringSession

from app.config import get_telegram_api
from app.utils.proxy_utils import build_proxy, log_proxy_usage


def create_client(account) -> TelegramClient:
    """
    account — asyncpg.Record or dict with keys:
        session_string,
        proxy_enabled, proxy_type, proxy_host, proxy_port,
        proxy_username, proxy_password
    """
    api_id, api_hash = get_telegram_api()
    session = StringSession(account["session_string"] or "")
    proxy = build_proxy(account) if account["proxy_enabled"] else None
    name = account.get("name") or str(account.get("id", "?"))[:8]
    log_proxy_usage(name, proxy)

    return TelegramClient(session, api_id, api_hash, proxy=proxy)
