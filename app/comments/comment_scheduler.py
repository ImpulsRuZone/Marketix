"""
Decides whether the account should comment on this post.

Rules:
  1. If today's sent count >= max_comments_per_day → skip
  2. Roll random float: act only if < daily_comment_percent / 100
"""

from uuid import UUID
import asyncpg

from app.database.repositories import get_comments_today_count
from app.utils.random_utils import should_act


async def should_comment(
    pool: asyncpg.Pool,
    account_id: UUID,
    settings: dict,
) -> bool:
    today_count = await get_comments_today_count(pool, account_id)

    if today_count >= settings["max_comments_per_day"]:
        return False

    return should_act(settings["daily_comment_percent"])
