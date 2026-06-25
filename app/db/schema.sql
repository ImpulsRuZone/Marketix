-- Supabase schema for multi-account Telegram commenter bot.
-- Run in Supabase SQL editor.

create extension if not exists pgcrypto;

create table if not exists public.accounts (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    phone text not null unique,
    api_id integer not null,
    api_hash text not null,
    session_string text not null,
    gpt_prompt text not null default '',
    status text not null default 'active' check (status in ('active', 'paused', 'disabled')),

    proxy_enabled boolean not null default false,
    proxy_type text check (proxy_type in ('socks5', 'socks4', 'http')),
    proxy_host text,
    proxy_port integer,
    proxy_username text,
    proxy_password text,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_accounts_status on public.accounts(status);

create table if not exists public.account_settings (
    id uuid primary key default gen_random_uuid(),
    account_id uuid not null references public.accounts(id) on delete cascade,
    daily_comment_percent integer not null default 30 check (daily_comment_percent between 0 and 100),
    max_comments_per_day integer not null default 20 check (max_comments_per_day >= 0),
    sleep_start_time time not null default '01:00:00',
    sleep_end_time time not null default '08:00:00',
    timezone text not null default 'UTC',
    join_delay_min_seconds integer not null default 120 check (join_delay_min_seconds >= 0),
    join_delay_max_seconds integer not null default 600 check (join_delay_max_seconds >= join_delay_min_seconds),
    comment_delay_min_seconds integer not null default 30 check (comment_delay_min_seconds >= 0),
    comment_delay_max_seconds integer not null default 180 check (comment_delay_max_seconds >= comment_delay_min_seconds),
    is_active boolean not null default true,
    updated_at timestamptz not null default now(),
    unique(account_id)
);

create table if not exists public.target_chats (
    id uuid primary key default gen_random_uuid(),
    chat_url text not null unique,
    chat_id text,
    title text,
    kind text not null default 'channel' check (kind in ('channel', 'group', 'supergroup')),
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists public.account_chats (
    id uuid primary key default gen_random_uuid(),
    account_id uuid not null references public.accounts(id) on delete cascade,
    chat_id uuid not null references public.target_chats(id) on delete cascade,
    status text not null default 'pending' check (status in ('pending', 'connected', 'failed', 'disabled')),
    last_join_attempt_at timestamptz,
    joined_at timestamptz,
    error_message text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(account_id, chat_id)
);

create index if not exists idx_account_chats_account_id on public.account_chats(account_id);
create index if not exists idx_account_chats_status on public.account_chats(status);

create table if not exists public.comments (
    id uuid primary key default gen_random_uuid(),
    account_id uuid not null references public.accounts(id) on delete cascade,
    chat_id text not null,
    post_id text not null,
    post_text text not null,
    generated_comment text not null,
    sent_comment text,
    status text not null default 'generated' check (status in ('generated', 'sent', 'failed', 'skipped')),
    error_message text,
    created_at timestamptz not null default now(),
    sent_at timestamptz,
    updated_at timestamptz not null default now()
);

create index if not exists idx_comments_account_id on public.comments(account_id);
create index if not exists idx_comments_status on public.comments(status);
create index if not exists idx_comments_sent_at on public.comments(sent_at);

create table if not exists public.logs (
    id uuid primary key default gen_random_uuid(),
    account_id uuid references public.accounts(id) on delete set null,
    level text not null check (level in ('info', 'warning', 'error')),
    event_type text not null,
    message text not null,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_logs_account_id on public.logs(account_id);
create index if not exists idx_logs_created_at on public.logs(created_at);

-- Optional row level security baseline (adjust to your auth model).
alter table public.accounts enable row level security;
alter table public.account_settings enable row level security;
alter table public.target_chats enable row level security;
alter table public.account_chats enable row level security;
alter table public.comments enable row level security;
alter table public.logs enable row level security;

drop policy if exists "service-role-full-access-accounts" on public.accounts;
create policy "service-role-full-access-accounts" on public.accounts
    for all to service_role
    using (true)
    with check (true);

drop policy if exists "service-role-full-access-account-settings" on public.account_settings;
create policy "service-role-full-access-account-settings" on public.account_settings
    for all to service_role
    using (true)
    with check (true);

drop policy if exists "service-role-full-access-target-chats" on public.target_chats;
create policy "service-role-full-access-target-chats" on public.target_chats
    for all to service_role
    using (true)
    with check (true);

drop policy if exists "service-role-full-access-account-chats" on public.account_chats;
create policy "service-role-full-access-account-chats" on public.account_chats
    for all to service_role
    using (true)
    with check (true);

drop policy if exists "service-role-full-access-comments" on public.comments;
create policy "service-role-full-access-comments" on public.comments
    for all to service_role
    using (true)
    with check (true);

drop policy if exists "service-role-full-access-logs" on public.logs;
create policy "service-role-full-access-logs" on public.logs
    for all to service_role
    using (true)
    with check (true);
