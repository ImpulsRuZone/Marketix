"""
Build Telethon-compatible proxy config from account record.
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def build_proxy(account) -> Optional[dict]:
    """
    Returns a proxy dict for Telethon if proxy_enabled is True.

    Dict format (python-socks / Telethon):
        proxy_type, addr, port, username, password, rdns
    """
    if not account["proxy_enabled"]:
        return None

    proxy_type = (account["proxy_type"] or "socks5").lower()
    if proxy_type not in ("socks5", "socks4", "http"):
        proxy_type = "socks5"

    return {
        "proxy_type": proxy_type,
        "addr":       account["proxy_host"],
        "port":       int(account["proxy_port"]),
        "username":   account["proxy_username"] or None,
        "password":   account["proxy_password"] or None,
        "rdns":       True,
    }


def proxy_label(proxy: dict) -> str:
    """Human-readable proxy string without password."""
    user = proxy.get("username")
    auth = f"{user}@" if user else ""
    return f"{proxy['proxy_type']}://{auth}{proxy['addr']}:{proxy['port']}"


def verify_proxy_backend() -> Tuple[bool, str]:
    """
    Telethon needs python-socks with asyncio extra for async proxy.
    Returns (ok, message).
    """
    try:
        import python_socks  # noqa: F401
    except ImportError:
        return False, "python-socks не установлен — proxy будет проигнорирован"

    try:
        import python_socks.async_.asyncio  # noqa: F401
        return True, "python-socks[asyncio] установлен — Telethon будет использовать proxy"
    except ImportError:
        return False, (
            "Установлен python-socks без asyncio. "
            "Выполни: pip3 install 'python-socks[asyncio]'"
        )


def log_proxy_usage(account_name: str, proxy: Optional[dict]) -> None:
    """Log proxy configuration before Telethon connect."""
    if not proxy:
        logger.info("[%s] Подключение напрямую (без proxy)", account_name)
        return

    ok, backend_msg = verify_proxy_backend()
    label = proxy_label(proxy)
    logger.info("[%s] Прокси: %s", account_name, label)
    logger.info("[%s] %s", account_name, backend_msg)
    if not ok:
        logger.warning(
            "[%s] Прокси, скорее всего, НЕ будет использован Telethon!", account_name
        )
