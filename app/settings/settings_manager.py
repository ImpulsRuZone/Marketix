"""
Loads and updates per-account settings from the database.
"""

from datetime import time
from typing import Optional
from uuid import UUID

import asyncpg

from app.database.db_types import as_db_uuid


DEFAULT_SETTINGS = {
    "daily_comment_percent":  30,
    "max_comments_per_day":   20,
    "sleep_start_time":       None,
    "sleep_end_time":         None,
    "timezone":               "UTC",
    "join_delay_min_seconds": 120,
    "join_delay_max_seconds": 600,
    "is_active":              True,
    "masslook_enabled":              False,
    "max_story_views_per_day":       100,
    "story_view_delay_min_seconds":  5,
    "story_view_delay_max_seconds":  30,
    "masslook_cycle_pause_min_seconds": 300,
    "masslook_cycle_pause_max_seconds": 900,
}


def merge_with_defaults(record) -> dict:
    """
    Merges a DB record (or None) with DEFAULT_SETTINGS.
    Returns a plain dict so callers don't depend on asyncpg internals.
    """
    result = dict(DEFAULT_SETTINGS)
    if record:
        for key in DEFAULT_SETTINGS:
            val = record.get(key)
            if val is not None:
                result[key] = val
    return result


async def get_settings(pool: asyncpg.Pool, account_id: UUID) -> dict:
    """Fetches settings for one account, falling back to defaults."""
    row = await pool.fetchrow(
        "SELECT * FROM account_settings WHERE account_id = $1",
        as_db_uuid(account_id),
    )
    return merge_with_defaults(row)


async def update_settings(
    pool: asyncpg.Pool,
    account_id: UUID,
    *,
    daily_comment_percent: Optional[int] = None,
    max_comments_per_day: Optional[int] = None,
    sleep_start_time: Optional[time] = None,
    sleep_end_time: Optional[time] = None,
    timezone: Optional[str] = None,
    join_delay_min_seconds: Optional[int] = None,
    join_delay_max_seconds: Optional[int] = None,
    is_active: Optional[bool] = None,
) -> None:
    """Upserts settings for one account. Only non-None values are updated."""
    await pool.execute("""
        INSERT INTO account_settings (account_id)
        VALUES ($1)
        ON CONFLICT (account_id) DO NOTHING
    """, as_db_uuid(account_id))

    fields = {
        "daily_comment_percent":  daily_comment_percent,
        "max_comments_per_day":   max_comments_per_day,
        "sleep_start_time":       sleep_start_time,
        "sleep_end_time":         sleep_end_time,
        "timezone":               timezone,
        "join_delay_min_seconds": join_delay_min_seconds,
        "join_delay_max_seconds": join_delay_max_seconds,
        "is_active":              is_active,
    }
    updates = {k: v for k, v in fields.items() if v is not None}
    if not updates:
        return

    set_clause = ", ".join(
        f"{col} = ${i + 2}" for i, col in enumerate(updates)
    )
    values = [as_db_uuid(account_id)] + list(updates.values())
    await pool.execute(
        f"UPDATE account_settings SET {set_clause}, updated_at = now() WHERE account_id = $1",
        *values,
    )
