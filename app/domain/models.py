from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional


@dataclass(slots=True)
class ProxyConfig:
    enabled: bool
    proxy_type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None


@dataclass(slots=True)
class AccountSettings:
    account_id: str
    daily_comment_percent: int
    max_comments_per_day: int
    sleep_start_time: time
    sleep_end_time: time
    timezone: str
    join_delay_min_seconds: int
    join_delay_max_seconds: int
    comment_delay_min_seconds: int
    comment_delay_max_seconds: int
    is_active: bool = True


@dataclass(slots=True)
class Account:
    id: str
    phone: str
    api_id: int
    api_hash: str
    session_string: str
    name: str
    gpt_prompt: str
    status: str
    proxy: ProxyConfig
    created_at: datetime
