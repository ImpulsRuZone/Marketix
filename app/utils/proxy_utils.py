"""
Build Telethon-compatible proxy config from account record.

Telethon supports two proxy backends:
  - python-socks (preferred, async-native) — expects a dict with string proxy_type
  - PySocks (legacy) — expects a tuple with socks.SOCKS5 integer constant

We always build the dict format; Telethon handles both.
"""

from typing import Optional


def build_proxy(account) -> Optional[dict]:
    """
    Returns a proxy dict for Telethon if proxy_enabled is True,
    otherwise returns None.

    Dict format (python-socks / Telethon):
        {
            'proxy_type': 'socks5' | 'socks4' | 'http',
            'addr':       host,
            'port':       port,
            'username':   username or None,
            'password':   password or None,
            'rdns':       True,
        }
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
