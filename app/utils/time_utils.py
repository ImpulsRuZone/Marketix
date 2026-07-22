"""Helpers for sleep-window detection."""

from datetime import datetime, time
from typing import Optional

try:
    import pytz
except ImportError:
    pytz = None  # type: ignore


def is_sleep_time(
    sleep_start: Optional[time],
    sleep_end: Optional[time],
    timezone: str = "UTC",
) -> bool:
    """
    Returns True if the current local time (in `timezone`) falls within
    the [sleep_start, sleep_end] window.
    Supports windows that cross midnight (e.g. 23:00 → 08:00).
    """
    if sleep_start is None or sleep_end is None:
        return False

    if pytz:
        try:
            tz = pytz.timezone(timezone)
        except Exception:
            tz = pytz.utc
        now = datetime.now(tz).time().replace(tzinfo=None)
    else:
        now = datetime.utcnow().time()

    if sleep_start <= sleep_end:
        return sleep_start <= now <= sleep_end
    else:
        # crosses midnight: e.g. 23:00 → 08:00
        return now >= sleep_start or now <= sleep_end


def seconds_until_wake(
    sleep_end: Optional[time],
    timezone: str = "UTC",
) -> int:
    """Returns seconds until sleep_end in the given timezone."""
    if sleep_end is None:
        return 0

    if pytz:
        try:
            tz = pytz.timezone(timezone)
        except Exception:
            tz = pytz.utc
        now_dt = datetime.now(tz)
    else:
        now_dt = datetime.utcnow()

    now_t = now_dt.time().replace(tzinfo=None)

    wake_dt = now_dt.replace(
        hour=sleep_end.hour,
        minute=sleep_end.minute,
        second=sleep_end.second,
        microsecond=0,
    )
    if wake_dt.time() <= now_t:
        from datetime import timedelta
        wake_dt += timedelta(days=1)

    delta = (wake_dt - now_dt.replace(tzinfo=None if pytz is None else wake_dt.tzinfo))
    return max(0, int(delta.total_seconds()))
