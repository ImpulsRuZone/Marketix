from __future__ import annotations

import random
from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.settings.settings_manager import SettingsManager


class CommentScheduler:
    @staticmethod
    def should_comment(post_roll: int, daily_comment_percent: int) -> bool:
        return post_roll <= daily_comment_percent

    @staticmethod
    def resolve_delay(min_seconds: int, max_seconds: int) -> int:
        return random.randint(min_seconds, max_seconds)

    @staticmethod
    def is_sleep_time(timezone: str, sleep_start: time, sleep_end: time) -> bool:
        now_local = datetime.now(ZoneInfo(timezone))
        return SettingsManager.is_sleep_time(now_local, sleep_start, sleep_end)
