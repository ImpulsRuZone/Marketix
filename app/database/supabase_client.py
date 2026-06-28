"""
Manages the asyncpg connection pool.
Works with Supabase (PostgreSQL) or any standard PostgreSQL server.
"""

import asyncpg
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def init_pool(database_url: str) -> asyncpg.Pool:
    global _pool
    # statement_cache_size=0 required for Supabase PgBouncer (transaction pooler)
    _pool = await asyncpg.create_pool(
        database_url,
        min_size=2,
        max_size=10,
        statement_cache_size=0,
    )
    logger.info("Database pool initialized")
    return _pool


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized. Call init_pool() first.")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")
