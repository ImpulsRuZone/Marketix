import asyncpg
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def get_pool(database_url: str) -> asyncpg.Pool:
    pool = await asyncpg.create_pool(database_url)
    await _ensure_tables(pool)
    return pool


async def _ensure_tables(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id          SERIAL PRIMARY KEY,
                created_at  TIMESTAMPTZ DEFAULT NOW(),
                account     TEXT,
                level       TEXT,
                event_type  TEXT,
                message     TEXT,
                channel     TEXT,
                username    TEXT,
                wait_seconds INTEGER
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id              SERIAL PRIMARY KEY,
                created_at      TIMESTAMPTZ DEFAULT NOW(),
                account         TEXT,
                channel_name    TEXT,
                channel_username TEXT,
                post_text       TEXT,
                comment         TEXT
            )
        """)


async def log_event(
    pool: asyncpg.Pool,
    level: str,
    event_type: str,
    message: str,
    channel: str = "",
    username: str = "",
    wait_seconds: Optional[int] = None,
    account: str = "",
) -> None:
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO events
                    (account, level, event_type, message, channel, username, wait_seconds)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                account, level, event_type, message, channel, username, wait_seconds,
            )
    except Exception as e:
        logger.error(f"db.log_event error: {e}")


async def log_comment(
    pool: asyncpg.Pool,
    channel_name: str,
    channel_username: str,
    post_text: str,
    comment: str,
    account: str = "",
) -> None:
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO comments
                    (account, channel_name, channel_username, post_text, comment)
                VALUES ($1, $2, $3, $4, $5)
                """,
                account, channel_name, channel_username, post_text, comment,
            )
    except Exception as e:
        logger.error(f"db.log_comment error: {e}")
