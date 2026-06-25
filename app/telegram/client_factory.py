from __future__ import annotations

from telethon import TelegramClient
from telethon.sessions import StringSession


def _build_proxy(account: dict) -> tuple | None:
    if not account.get("proxy_enabled"):
        return None

    proxy_type = (account.get("proxy_type") or "").lower()
    host = account.get("proxy_host")
    port = account.get("proxy_port")
    username = account.get("proxy_username")
    password = account.get("proxy_password")

    if not host or not port:
        raise ValueError("Proxy is enabled but host/port are missing")

    # Telethon uses PySocks constants for proxy type.
    import socks

    type_mapping = {
        "socks5": socks.SOCKS5,
        "socks4": socks.SOCKS4,
        "http": socks.HTTP,
    }
    if proxy_type not in type_mapping:
        raise ValueError(f"Unsupported proxy type: {proxy_type}")

    return (type_mapping[proxy_type], host, int(port), True, username, password)


def build_client(account: dict) -> TelegramClient:
    proxy = _build_proxy(account)
    return TelegramClient(
        session=StringSession(account["session_string"]),
        api_id=int(account["api_id"]),
        api_hash=account["api_hash"],
        proxy=proxy,
    )
