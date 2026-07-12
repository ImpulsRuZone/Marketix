"""Helpers for passing values to asyncpg with mixed Supabase column types."""

from typing import Any, Optional


def as_db_uuid(value: Any) -> Optional[str]:
    """UUID columns stored as text in some Supabase schemas need plain strings."""
    if value is None:
        return None
    return str(value)
