"""
Scheduling and limits for mass-looking.
"""

from uuid import UUID

import asyncpg

from app.database import repositories as repo
from app.utils.time_utils import is_sleep_time


async def can_view_more(
    pool: asyncpg.Pool,
    account_id: UUID,
    settings: dict,
) -> bool:
    """Returns False if account is inactive, sleeping, or hit daily limit."""
    if not settings.get("masslook_enabled", False):
        return False

    if not settings.get("is_active", True):
        return False

    if is_sleep_time(
        settings.get("sleep_start_time"),
        settings.get("sleep_end_time"),
        settings.get("timezone", "UTC"),
    ):
        return False

    max_per_day = settings.get("max_story_views_per_day", 100)
    today_count = await repo.get_story_views_today_count(pool, account_id)
    return today_count < max_per_day
