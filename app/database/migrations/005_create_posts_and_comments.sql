-- Create posts and comments tables if missing (partial Supabase schema).

create extension if not exists "pgcrypto";

create table if not exists posts (
    id               uuid primary key default gen_random_uuid(),
    chat_id          uuid not null references target_chats(id) on delete cascade,
    telegram_post_id bigint not null,
    post_text        text,
    post_date        timestamptz,
    created_at       timestamptz default now(),
    unique (chat_id, telegram_post_id)
);

create table if not exists comments (
    id                 uuid primary key default gen_random_uuid(),
    account_id         uuid not null references accounts(id) on delete cascade,
    chat_id            uuid references target_chats(id) on delete set null,
    post_id            uuid references posts(id) on delete set null,
    generated_comment  text,
    sent_comment       text,
    status             text default 'generated',
    error_message      text,
    created_at         timestamptz default now(),
    sent_at            timestamptz
);

create index if not exists idx_posts_chat       on posts(chat_id);
create index if not exists idx_comments_account on comments(account_id);
create index if not exists idx_comments_created on comments(created_at);
