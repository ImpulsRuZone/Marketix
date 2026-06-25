from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo


class SettingsValidationError(ValueError):
    pass


class SettingsManager:
    @staticmethod
    def validate_comment_limits(daily_comment_percent: int, max_comments_per_day: int) -> None:
        if daily_comment_percent < 0 or daily_comment_percent > 100:
            raise SettingsValidationError("daily_comment_percent must be in [0, 100]")
        if max_comments_per_day < 0:
            raise SettingsValidationError("max_comments_per_day must be >= 0")

    @staticmethod
    def validate_delays(min_seconds: int, max_seconds: int, field_name: str) -> None:
        if min_seconds < 0 or max_seconds < 0:
            raise SettingsValidationError(f"{field_name}: delay values must be >= 0")
        if min_seconds > max_seconds:
            raise SettingsValidationError(f"{field_name}: min delay must be <= max delay")

    @staticmethod
    def validate_sleep_window(sleep_start_time: time, sleep_end_time: time) -> None:
        if sleep_start_time == sleep_end_time:
            raise SettingsValidationError("sleep_start_time and sleep_end_time cannot be identical")

    @staticmethod
    def now_in_tz(timezone: str) -> datetime:
        return datetime.now(ZoneInfo(timezone))

    @staticmethod
    def is_sleep_time(now_local: datetime, sleep_start: time, sleep_end: time) -> bool:
        current = now_local.time()
        if sleep_start < sleep_end:
            return sleep_start <= current < sleep_end
        return current >= sleep_start or current < sleep_end
