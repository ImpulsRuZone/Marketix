"""
Unified logger: writes to stdout and optionally to the DB logs table.
"""

import logging
import asyncio
from typing import Optional
from uuid import UUID


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


class DBLogger:
    """
    Wraps a standard logger and mirrors WARNING/ERROR events to the DB.
    Pass pool=None to disable DB logging.
    """

    def __init__(self, name: str, account_id: Optional[UUID] = None, pool=None):
        self._log = logging.getLogger(name)
        self.account_id = account_id
        self.pool = pool

    # ── public helpers ──────────────────────────────────────────────

    def info(self, event_type: str, msg: str, payload: Optional[dict] = None) -> None:
        self._log.info(f"[{event_type}] {msg}")
        if self.pool:
            self._fire(self.pool, "INFO", event_type, msg, self.account_id, payload)

    def warning(self, event_type: str, msg: str, payload: Optional[dict] = None) -> None:
        self._log.warning(f"[{event_type}] {msg}")
        if self.pool:
            self._fire(self.pool, "WARNING", event_type, msg, self.account_id, payload)

    def error(self, event_type: str, msg: str, payload: Optional[dict] = None) -> None:
        self._log.error(f"[{event_type}] {msg}")
        if self.pool:
            self._fire(self.pool, "ERROR", event_type, msg, self.account_id, payload)

    # ── internal ────────────────────────────────────────────────────

    @staticmethod
    def _fire(pool, level, event_type, message, account_id, payload) -> None:
        """Schedule a DB write without blocking the caller."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(
                    _write_db_log(pool, level, event_type, message, account_id, payload)
                )
        except Exception:
            pass


async def _write_db_log(pool, level, event_type, message, account_id, payload) -> None:
    from app.database.repositories import write_log
    await write_log(pool, level, event_type, message, account_id, payload)
