-- =============================================
-- Neurocomment Bot — Supabase / PostgreSQL schema
-- Run once: psql $DATABASE_URL -f schema.sql
-- =============================================

create extension if not exists "pgcrypto";

-- ------------------------------------------
-- accounts
-- ------------------------------------------
create table if not exists accounts (
    id               uuid primary key default gen_random_uuid(),
    name             text,
    phone            text not null,
    api_id           integer not null,   -- копия из .env (для справки)
    api_hash         text not null,      -- копия из .env (для справки)
    session_string   text not null,
    gpt_prompt       text,
    proxy_enabled    boolean default false,
    proxy_type       text,           -- socks5 | http
    proxy_host       text,
    proxy_port       integer,
    proxy_username   text,
    proxy_password   text,
    status           text default 'active',   -- active | paused | banned
    created_at       timestamptz default now(),
    updated_at       timestamptz default now()
);

-- ------------------------------------------
-- account_settings
-- ------------------------------------------
create table if not exists account_settings (
    id                        uuid primary key default gen_random_uuid(),
    account_id                uuid not null references accounts(id) on delete cascade,
    daily_comment_percent     integer default 30,
    max_comments_per_day      integer default 20,
    sleep_start_time          time,
    sleep_end_time            time,
    timezone                  text default 'UTC',
    join_delay_min_seconds    integer default 120,
    join_delay_max_seconds    integer default 600,
    is_active                 boolean default true,
    created_at                timestamptz default now(),
    updated_at                timestamptz default now(),
    unique (account_id)
);

-- ------------------------------------------
-- target_chats
-- ------------------------------------------
create table if not exists target_chats (
    id           uuid primary key default gen_random_uuid(),
    chat_url     text not null unique,
    chat_id      bigint,
    username     text,
    title        text,
    type         text,           -- channel | group
    is_active    boolean default true,
    created_at   timestamptz default now(),
    updated_at   timestamptz default now()
);

-- ------------------------------------------
-- account_chats  (many-to-many)
-- ------------------------------------------
create table if not exists account_chats (
    id                    uuid primary key default gen_random_uuid(),
    account_id            uuid not null references accounts(id) on delete cascade,
    chat_id               uuid not null references target_chats(id) on delete cascade,
    account_name          text,
    chat_title            text,
    status                text default 'pending',  -- pending | joined | failed | requested | excluded
    last_join_attempt_at  timestamptz,
    joined_at             timestamptz,
    error_message         text,
    created_at            timestamptz default now(),
    updated_at            timestamptz default now(),
    unique (account_id, chat_id)
);

-- ------------------------------------------
-- posts
-- ------------------------------------------
create table if not exists posts (
    id               uuid primary key default gen_random_uuid(),
    chat_id          uuid not null references target_chats(id) on delete cascade,
    telegram_post_id bigint not null,
    post_text        text,
    post_date        timestamptz,
    created_at       timestamptz default now(),
    unique (chat_id, telegram_post_id)
);

-- ------------------------------------------
-- comments
-- ------------------------------------------
create table if not exists comments (
    id                 uuid primary key default gen_random_uuid(),
    account_id         uuid not null references accounts(id) on delete cascade,
    chat_id            uuid references target_chats(id) on delete set null,
    post_id            uuid references posts(id) on delete set null,
    account_name       text,
    chat_title         text,
    post_text          text,
    generated_comment  text,
    sent_comment       text,
    status             text default 'generated',  -- generated | sent | failed
    error_message      text,
    created_at         timestamptz default now(),
    sent_at            timestamptz
);

-- Supabase UI: open comments_readable (no UUID columns, Moscow send time).
create or replace view comments_readable as
select
    to_char(
        c.sent_at at time zone 'Europe/Moscow',
        'DD.MM.YYYY HH24:MI:SS'
    ) as sent_at_moscow,
    coalesce(c.account_name, a.name) as account_name,
    coalesce(c.chat_title, tc.title) as chat_title,
    c.post_text,
    c.generated_comment,
    c.status,
    c.sent_comment
from comments c
left join accounts a on a.id = c.account_id::uuid
left join target_chats tc on tc.id = c.chat_id::uuid
order by c.sent_at desc nulls last, c.created_at desc;

-- ------------------------------------------
-- logs
-- ------------------------------------------
create table if not exists logs (
    id           uuid primary key default gen_random_uuid(),
    account_id   uuid references accounts(id) on delete set null,
    level        text not null,       -- INFO | WARNING | ERROR
    event_type   text not null,
    message      text,
    payload      jsonb,
    created_at   timestamptz default now()
);

-- ------------------------------------------
-- indexes
-- ------------------------------------------
create index if not exists idx_account_chats_account on account_chats(account_id);
create index if not exists idx_account_chats_chat    on account_chats(chat_id);
create index if not exists idx_comments_account      on comments(account_id);
create index if not exists idx_comments_created      on comments(created_at);
create index if not exists idx_logs_account          on logs(account_id);
create index if not exists idx_logs_created          on logs(created_at);
create index if not exists idx_posts_chat            on posts(chat_id);

-- ── Patches for databases created from an older/partial schema ──
alter table target_chats add column if not exists username text;
alter table target_chats add column if not exists title text;
alter table target_chats add column if not exists type text;
alter table target_chats add column if not exists updated_at timestamptz default now();
alter table account_chats add column if not exists updated_at timestamptz default now();
alter table account_chats add column if not exists account_name text;
alter table account_chats add column if not exists chat_title text;
alter table logs alter column payload drop not null;
alter table logs drop constraint if exists logs_level_check;
alter table logs add constraint logs_level_check check (level in ('info', 'warning', 'error'));

alter table account_chats drop constraint if exists account_chats_status_check;
alter table account_chats add constraint account_chats_status_check
    check (status in ('pending', 'joined', 'failed', 'requested', 'excluded'));
