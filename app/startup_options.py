"""
Startup options: whether to join new channels on bot launch.

Interactive (TTY): numbered menu 1=Да, 2=Нет
systemd / no TTY: JOIN_ON_STARTUP in .env (default: false)
CLI: --join / --no-join
"""

from __future__ import annotations

import os
import sys
from typing import Optional


def _normalize(val: str) -> str:
    return val.strip().replace("\r", "").replace("\ufeff", "")


def _readline() -> str:
    raw = sys.stdin.buffer.readline()
    for enc in ("utf-8", "cp1251", "latin-1"):
        try:
            return _normalize(raw.decode(enc))
        except UnicodeDecodeError:
            continue
    return _normalize(raw.decode("latin-1", errors="replace"))


def _ask(prompt: str) -> str:
    sys.stdout.write(prompt)
    sys.stdout.flush()
    return _readline()


def _parse_env_bool(value: str) -> Optional[bool]:
    val = _normalize(value).lower()
    if val in ("1", "true", "yes", "y", "да", "д"):
        return True
    if val in ("0", "false", "no", "n", "нет", "н"):
        return False
    return None


def _ask_join_interactive() -> bool:
    print("\nВступать в новые каналы из списка target_chats?", flush=True)
    print("  1) Да — вступить в каналы, где аккаунт ещё не состоит", flush=True)
    print("  2) Нет — только слушать посты (без новых вступлений)", flush=True)

    while True:
        raw = _ask("Выбери [1-2]: ")
        if raw == "1":
            return True
        if raw == "2":
            return False
        print("  Нужно число 1 или 2", flush=True)


def resolve_join_on_startup(cli_join: Optional[bool] = None) -> bool:
    """
    Decide whether join_manager should run on this startup.

    Priority: CLI flag → JOIN_ON_STARTUP env → interactive prompt → False.
    """
    if cli_join is not None:
        return cli_join

    env_val = os.getenv("JOIN_ON_STARTUP", "")
    if env_val:
        parsed = _parse_env_bool(env_val)
        if parsed is not None:
            return parsed

    if sys.stdin.isatty():
        return _ask_join_interactive()

    return False
