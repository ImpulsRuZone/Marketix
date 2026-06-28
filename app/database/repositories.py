"""
Database repository layer. All SQL queries live here.
"""

import json
import logging
from datetime import datetime, date
from typing import Any, Optional, List, Tuple
from uuid import UUID

import asyncpg

from app.database.db_types import as_db_uuid

logger = logging.getLogger(__name__)


def _db_uuid(value: Any) -> Optional[str]:
    return as_db_uuid(value)


# ──────────────────────────────────────────────
# Accounts
# ──────────────────────────────────────────────

async def get_active_accounts(pool: asyncpg.Pool) -> List[asyncpg.Record]:
    """Returns all accounts with status='active' joined with their settings."""
    return await pool.fetch("""
        SELECT
            a.*,
            s.daily_comment_percent,
            s.max_comments_per_day,
            s.sleep_start_time,
            s.sleep_end_time,
            s.timezone,
            s.join_delay_min_seconds,
            s.join_delay_max_seconds,
            s.is_active
        FROM accounts a
        LEFT JOIN account_settings s ON s.account_id = a.id
        WHERE a.status = 'active'
    """)


async def get_account_by_phone(pool: asyncpg.Pool, phone: str) -> Optional[asyncpg.Record]:
    return await pool.fetchrow("SELECT * FROM accounts WHERE phone = $1", phone)


async def create_account(
    pool: asyncpg.Pool,
    name: str,
    phone: str,
    session_string: str,
    gpt_prompt: Optional[str] = None,
    proxy_enabled: bool = False,
    proxy_type: Optional[str] = None,
    proxy_host: Optional[str] = None,
    proxy_port: Optional[int] = None,
    proxy_username: Optional[str] = None,
    proxy_password: Optional[str] = None,
) -> asyncpg.Record:
    from app.config import get_telegram_api
    api_id, api_hash = get_telegram_api()

    async with pool.acquire() as conn:
        account = await conn.fetchrow("""
            INSERT INTO accounts
                (name, phone, api_id, api_hash, session_string, gpt_prompt,
                 proxy_enabled, proxy_type, proxy_host, proxy_port,
                 proxy_username, proxy_password)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            RETURNING *
        """, name, phone, api_id, api_hash, session_string, gpt_prompt,
            proxy_enabled, proxy_type, proxy_host, proxy_port,
            proxy_username, proxy_password)

        # Create default settings
        await conn.execute("""
            INSERT INTO account_settings (account_id)
            VALUES ($1)
            ON CONFLICT (account_id) DO NOTHING
        """, _db_uuid(account["id"]))

    return account


async def update_session_string(pool: asyncpg.Pool, account_id: UUID, session_string: str) -> None:
    await pool.execute("""
        UPDATE accounts
        SET session_string = $1, updated_at = now()
        WHERE id = $2
    """, session_string, _db_uuid(account_id))


async def update_account_status(pool: asyncpg.Pool, account_id: UUID, status: str) -> None:
    await pool.execute("""
        UPDATE accounts SET status = $1, updated_at = now() WHERE id = $2
    """, status, _db_uuid(account_id))


# ──────────────────────────────────────────────
# Target chats
# ──────────────────────────────────────────────

async def get_active_target_chats(pool: asyncpg.Pool) -> List[asyncpg.Record]:
    return await pool.fetch("SELECT * FROM target_chats WHERE is_active = true")


async def get_joinable_target_chats(pool: asyncpg.Pool) -> List[asyncpg.Record]:
    """Channels to join and monitor. Excludes auto-created linked groups (id:…)."""
    return await pool.fetch("""
        SELECT * FROM target_chats
        WHERE is_active = true
          AND chat_url NOT LIKE 'id:%'
    """)


async def upsert_target_chat(
    pool: asyncpg.Pool,
    chat_url: str,
    chat_id: Optional[int] = None,
    username: Optional[str] = None,
    title: Optional[str] = None,
    chat_type: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> asyncpg.Record:
    # Some DB setups store telegram chat_id as text, not bigint
    chat_id_db = str(chat_id) if chat_id is not None else None
    active_db = True if is_active is None else is_active

    return await pool.fetchrow("""
        INSERT INTO target_chats (chat_url, chat_id, username, title, type, is_active)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (chat_url) DO UPDATE
            SET chat_id   = COALESCE(EXCLUDED.chat_id, target_chats.chat_id),
                username  = COALESCE(EXCLUDED.username, target_chats.username),
                title     = COALESCE(EXCLUDED.title, target_chats.title),
                type      = COALESCE(EXCLUDED.type, target_chats.type),
                is_active = CASE
                    WHEN $6 = false THEN false
                    ELSE target_chats.is_active
                END
        RETURNING *
    """, chat_url, chat_id_db, username, title, chat_type, active_db)


async def deactivate_target_chat(
    pool: asyncpg.Pool,
    *,
    chat_url: Optional[str] = None,
    telegram_chat_id: Optional[int] = None,
) -> None:
    """Marks channel as inactive so it won't be monitored after restart."""
    if chat_url:
        await pool.execute(
            "UPDATE target_chats SET is_active = false WHERE chat_url = $1",
            chat_url,
        )
        return
    if telegram_chat_id is not None:
        await pool.execute(
            "UPDATE target_chats SET is_active = false WHERE chat_id = $1",
            str(telegram_chat_id),
        )


async def get_excluded_target_chat_ids(
    pool: asyncpg.Pool,
    account_id: UUID,
) -> set:
    """Target chat UUIDs excluded from monitoring for this account only."""
    rows = await pool.fetch("""
        SELECT chat_id
        FROM account_chats
        WHERE account_id = $1
          AND (
              status = 'excluded'
              OR (status = 'failed' AND error_message LIKE '[excluded]%')
          )
    """, _db_uuid(account_id))
    return {str(row["chat_id"]) for row in rows}


async def record_channel_exclusion(
    pool: asyncpg.Pool,
    account_id: UUID,
    error_message: str,
    *,
    chat_db_id: Optional[UUID] = None,
    chat_url: Optional[str] = None,
    telegram_chat_id: Optional[int] = None,
    username: Optional[str] = None,
    title: Optional[str] = None,
    account_name: Optional[str] = None,
) -> Optional[UUID]:
    """
    Persist per-account channel exclusion in account_chats and logs.
    Does NOT deactivate target_chats globally — other accounts keep listening.
    Required when linked group returns 'private and you lack permission'.
    """
    url = chat_url
    if not url:
        if username:
            url = f"@{username.lstrip('@')}"
        elif telegram_chat_id is not None:
            url = f"id:{telegram_chat_id}"

    target_row = await upsert_target_chat(
        pool,
        chat_url=url,
        chat_id=telegram_chat_id,
        username=username,
        title=title,
        chat_type="channel",
    )
    target_id = chat_db_id or target_row["id"]

    await upsert_account_chat(
        pool,
        account_id,
        target_id,
        "excluded",
        error_message=error_message,
        account_name=account_name,
        chat_title=title,
    )

    label = title or url or str(telegram_chat_id)
    await write_log(
        pool,
        "warning",
        "канал_исключён",
        f"[{label}] Исключён для аккаунта: {error_message}",
        account_id,
        payload={
            "account_id": _db_uuid(account_id),
            "chat_url": url,
            "telegram_chat_id": telegram_chat_id,
            "target_chat_id": _db_uuid(target_id),
            "error": error_message,
            "scope": "account",
        },
    )
    return target_id


# ──────────────────────────────────────────────
# Account chats
# ──────────────────────────────────────────────

async def get_account_chats(pool: asyncpg.Pool, account_id: UUID) -> List[asyncpg.Record]:
    return await pool.fetch("""
        SELECT ac.*, tc.chat_url, tc.title AS target_chat_title
        FROM account_chats ac
        JOIN target_chats tc ON tc.id = ac.chat_id
        WHERE ac.account_id = $1
    """, _db_uuid(account_id))


async def _resolve_account_chat_names(
    pool: asyncpg.Pool,
    account_id: UUID,
    chat_id: UUID,
    account_name: Optional[str] = None,
    chat_title: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    if account_name and chat_title:
        return account_name, chat_title

    row = await pool.fetchrow("""
        SELECT a.name AS account_name, tc.title AS chat_title
        FROM accounts a
        CROSS JOIN target_chats tc
        WHERE a.id = $1 AND tc.id = $2
    """, _db_uuid(account_id), _db_uuid(chat_id))

    if not row:
        return account_name, chat_title

    return (
        account_name or row.get("account_name"),
        chat_title or row.get("chat_title"),
    )


async def upsert_account_chat(
    pool: asyncpg.Pool,
    account_id: UUID,
    chat_id: UUID,
    status: str,
    error_message: Optional[str] = None,
    joined_at: Optional[datetime] = None,
    account_name: Optional[str] = None,
    chat_title: Optional[str] = None,
) -> None:
    status_db = status.lower()
    if status_db not in ("pending", "joined", "failed", "requested", "excluded"):
        status_db = "pending"

    account_name, chat_title = await _resolve_account_chat_names(
        pool, account_id, chat_id, account_name, chat_title,
    )

    try:
        await _upsert_account_chat_row(
            pool, account_id, chat_id, status_db, joined_at, error_message,
            account_name, chat_title,
        )
    except Exception as e:
        err = str(e)
        if status_db == "excluded" and "account_chats_status_check" in err:
            marked = f"[excluded] {error_message}" if error_message else "[excluded]"
            await _upsert_account_chat_row(
                pool, account_id, chat_id, "failed", joined_at, marked,
                account_name, chat_title, with_names=True,
            )
            return
        if "account_name" not in err and "chat_title" not in err:
            raise
        await _upsert_account_chat_row(
            pool, account_id, chat_id, status_db, joined_at, error_message,
            None, None, with_names=False,
        )


async def _upsert_account_chat_row(
    pool: asyncpg.Pool,
    account_id: UUID,
    chat_id: UUID,
    status_db: str,
    joined_at: Optional[datetime],
    error_message: Optional[str],
    account_name: Optional[str],
    chat_title: Optional[str],
    with_names: bool = True,
) -> None:
    if with_names and account_name is not None:
        await pool.execute("""
            INSERT INTO account_chats
                (account_id, chat_id, account_name, chat_title,
                 status, last_join_attempt_at, joined_at, error_message)
            VALUES ($1, $2, $3, $4, $5, now(), $6, $7)
            ON CONFLICT (account_id, chat_id) DO UPDATE
                SET status               = EXCLUDED.status,
                    account_name         = COALESCE(EXCLUDED.account_name, account_chats.account_name),
                    chat_title           = COALESCE(EXCLUDED.chat_title, account_chats.chat_title),
                    last_join_attempt_at = now(),
                    joined_at            = COALESCE(EXCLUDED.joined_at, account_chats.joined_at),
                    error_message        = EXCLUDED.error_message
        """, _db_uuid(account_id), _db_uuid(chat_id), account_name, chat_title,
            status_db, joined_at, error_message)
        return

    await pool.execute("""
        INSERT INTO account_chats
            (account_id, chat_id, status, last_join_attempt_at, joined_at, error_message)
        VALUES ($1, $2, $3, now(), $4, $5)
        ON CONFLICT (account_id, chat_id) DO UPDATE
            SET status               = EXCLUDED.status,
                last_join_attempt_at = now(),
                joined_at            = COALESCE(EXCLUDED.joined_at, account_chats.joined_at),
                error_message        = EXCLUDED.error_message
    """, _db_uuid(account_id), _db_uuid(chat_id), status_db, joined_at, error_message)


# ──────────────────────────────────────────────
# Posts
# ──────────────────────────────────────────────

async def upsert_post(
    pool: asyncpg.Pool,
    chat_id: UUID,
    telegram_post_id: int,
    post_text: str,
    post_date: datetime,
) -> asyncpg.Record:
    return await pool.fetchrow("""
        INSERT INTO posts (chat_id, telegram_post_id, post_text, post_date)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (chat_id, telegram_post_id) DO UPDATE
            SET post_text = EXCLUDED.post_text
        RETURNING *
    """, _db_uuid(chat_id), telegram_post_id, post_text, post_date)


# ──────────────────────────────────────────────
# Comments
# ──────────────────────────────────────────────

async def create_comment(
    pool: asyncpg.Pool,
    account_id: UUID,
    chat_id: Optional[UUID],
    post_id: Optional[UUID],
    generated_comment: str,
    post_text: Optional[str] = None,
    account_name: Optional[str] = None,
    chat_title: Optional[str] = None,
) -> asyncpg.Record:
    # Some Supabase schemas require post_text NOT NULL on comments
    post_text_db = post_text if post_text is not None else generated_comment

    return await pool.fetchrow("""
        INSERT INTO comments
            (account_id, chat_id, post_id, generated_comment, post_text,
             account_name, chat_title)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING *
    """, _db_uuid(account_id), _db_uuid(chat_id), _db_uuid(post_id),
        generated_comment, post_text_db, account_name, chat_title)


async def create_comment_legacy(
    pool: asyncpg.Pool,
    account_id: UUID,
    chat_id: Optional[UUID],
    post_id: Optional[UUID],
    generated_comment: str,
) -> asyncpg.Record:
    """Fallback for schemas without comments.post_text column."""
    return await pool.fetchrow("""
        INSERT INTO comments (account_id, chat_id, post_id, generated_comment)
        VALUES ($1, $2, $3, $4)
        RETURNING *
    """, _db_uuid(account_id), _db_uuid(chat_id), _db_uuid(post_id), generated_comment)


async def mark_comment_sent(
    pool: asyncpg.Pool,
    comment_id,
    sent_comment: str,
) -> None:
    await pool.execute("""
        UPDATE comments
        SET status = 'sent', sent_comment = $1, sent_at = now()
        WHERE id = $2
    """, sent_comment, _db_uuid(comment_id))


async def mark_comment_failed(
    pool: asyncpg.Pool,
    comment_id,
    error_message: str,
) -> None:
    await pool.execute("""
        UPDATE comments
        SET status = 'failed', error_message = $1
        WHERE id = $2
    """, error_message, _db_uuid(comment_id))


async def get_comments_today_count(pool: asyncpg.Pool, account_id: UUID) -> int:
    row = await pool.fetchrow("""
        SELECT COUNT(*) as cnt
        FROM comments
        WHERE account_id = $1
          AND status = 'sent'
          AND sent_at >= date_trunc('day', now())
    """, _db_uuid(account_id))
    return row["cnt"] if row else 0


# ──────────────────────────────────────────────
# Logs
# ──────────────────────────────────────────────

async def write_log(
    pool: asyncpg.Pool,
    level: str,
    event_type: str,
    message: str,
    account_id: Optional[UUID] = None,
    payload: Optional[dict] = None,
) -> None:
    # DB check constraint expects lowercase: info | warning | error
    level_db = level.lower()
    if level_db not in ("info", "warning", "error"):
        level_db = "info"

    try:
        await pool.execute("""
            INSERT INTO logs (account_id, level, event_type, message, payload)
            VALUES ($1, $2, $3, $4, $5::jsonb)
        """, _db_uuid(account_id), level_db, event_type, message,
            json.dumps(payload if payload is not None else {}))
    except Exception as e:
        logger.error(f"Не удалось записать лог в БД: {e}")
