from __future__ import annotations

import logging
from typing import Any

from app.db.repositories import LogRepository


class AccountLogger:
    """Writes logs both locally and to Supabase."""

    def __init__(self, repository: LogRepository) -> None:
        self.repository = repository
        self.console = logging.getLogger("multiaccount-bot")
        if not self.console.handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    def info(self, account_id: str, event_type: str, message: str, payload: dict[str, Any] | None = None) -> None:
        self.console.info("[%s] %s", account_id, message)
        self.repository.write(account_id, "info", event_type, message, payload)

    def warning(
        self, account_id: str, event_type: str, message: str, payload: dict[str, Any] | None = None
    ) -> None:
        self.console.warning("[%s] %s", account_id, message)
        self.repository.write(account_id, "warning", event_type, message, payload)

    def error(self, account_id: str, event_type: str, message: str, payload: dict[str, Any] | None = None) -> None:
        self.console.error("[%s] %s", account_id, message)
        self.repository.write(account_id, "error", event_type, message, payload)
