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
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_accounts (
                name        TEXT PRIMARY KEY,
                phone       TEXT DEFAULT '',
                created_at  TIMESTAMPTZ DEFAULT NOW(),
                updated_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS account_channels (
                id          SERIAL PRIMARY KEY,
                account     TEXT NOT NULL,
                channel     TEXT NOT NULL,
                priority    TEXT DEFAULT 'Средний',
                is_active   BOOLEAN DEFAULT TRUE,
                note        TEXT DEFAULT '',
                created_at  TIMESTAMPTZ DEFAULT NOW(),
                updated_at  TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(account, channel)
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_account_channels_account
            ON account_channels(account)
        """)


async def log_event(
    pool,
    level: str,
    event_type: str,
    message: str,
    channel: str = "",
    username: str = "",
    wait_seconds: Optional[int] = None,
    account: str = "",
) -> None:
    if pool is None:
        return
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
    pool,
    channel_name: str,
    channel_username: str,
    post_text: str,
    comment: str,
    account: str = "",
) -> None:
    if pool is None:
        return
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


async def upsert_account(pool, name: str, phone: str = "") -> None:
    if pool is None:
        return
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO bot_accounts (name, phone)
            VALUES ($1, $2)
            ON CONFLICT (name) DO UPDATE
            SET phone = EXCLUDED.phone,
                updated_at = NOW()
            """,
            name,
            phone,
        )


async def sync_channels_from_rows(pool, account: str, rows) -> None:
    if pool is None:
        return

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM account_channels WHERE account = $1", account)
            for row in rows:
                await conn.execute(
                    """
                    INSERT INTO account_channels (account, channel, priority, is_active, note)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    account,
                    row.channel,
                    row.priority,
                    row.is_active,
                    row.note,
                )


async def get_active_channels(pool, account: str) -> list[str]:
    if pool is None:
        return []

    async with pool.acquire() as conn:
        records = await conn.fetch(
            """
            SELECT channel
            FROM account_channels
            WHERE account = $1 AND is_active = TRUE
            ORDER BY
                CASE priority
                    WHEN 'Высокий' THEN 1
                    WHEN 'Средний' THEN 2
                    WHEN 'Низкий' THEN 3
                    ELSE 4
                END,
                channel
            """,
            account,
        )
    return [r["channel"] for r in records]
