"""Build Telethon-compatible proxy tuple from account record."""

from typing import Optional, Tuple


def build_proxy(account) -> Optional[Tuple]:
    """
    Returns a proxy tuple for Telethon if proxy_enabled is True,
    otherwise returns None.

    Telethon proxy format: (type, host, port, True, username, password)
    where type is one of: socks.SOCKS5, socks.SOCKS4, socks.HTTP
    """
    if not account["proxy_enabled"]:
        return None

    try:
        import socks
    except ImportError:
        raise ImportError(
            "PySocks is required for proxy support. "
            "Install it with: pip install PySocks"
        )

    proxy_type_map = {
        "socks5": socks.SOCKS5,
        "socks4": socks.SOCKS4,
        "http":   socks.HTTP,
    }

    raw_type = (account["proxy_type"] or "socks5").lower()
    proxy_type = proxy_type_map.get(raw_type, socks.SOCKS5)

    return (
        proxy_type,
        account["proxy_host"],
        account["proxy_port"],
        True,
        account["proxy_username"] or None,
        account["proxy_password"] or None,
    )
