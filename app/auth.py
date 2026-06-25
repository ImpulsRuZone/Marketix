from __future__ import annotations

import logging
import os
from typing import Any

import socks
from telethon import TelegramClient

logger = logging.getLogger(__name__)


def create_client(acc_config: dict[str, Any]) -> TelegramClient:
    """Create a Telethon client using a file session under project data/.

    This intentionally follows the previously working client creation pattern:
    data/session_<session_name> + optional per-account proxy.
    """

    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_path, "data")
    os.makedirs(data_dir, exist_ok=True)

    session_path = os.path.join(data_dir, f"session_{acc_config['session_name']}")
    logger.info("DEBUG: Попытка инициализации сессии по пути: %s", session_path)

    proxy = None
    if acc_config.get("proxy"):
        p = acc_config["proxy"]
        proxy_type = (p.get("proxy_type") or "").lower()
        if proxy_type == "socks5":
            ptype = socks.SOCKS5
        elif proxy_type == "socks4":
            ptype = socks.SOCKS4
        elif proxy_type == "http":
            ptype = socks.HTTP
        else:
            raise ValueError("proxy_type must be socks5/socks4/http")

        proxy = (
            ptype,
            p["addr"],
            int(p["port"]),
            True,
            p.get("username"),
            p.get("password"),
        )

    return TelegramClient(
        session_path,
        int(acc_config["api_id"]),
        acc_config["api_hash"],
        proxy=proxy,
    )
