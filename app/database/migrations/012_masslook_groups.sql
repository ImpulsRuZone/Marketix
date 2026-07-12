-- Groups for mass-looking: join groups, scan participants, like stories.

CREATE TABLE IF NOT EXISTS masslook_groups (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    group_url    text NOT NULL UNIQUE,
    telegram_id  bigint,
    username     text,
    title        text,
    is_active    boolean DEFAULT true,
    created_at   timestamptz DEFAULT now(),
    updated_at   timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS masslook_account_groups (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id            uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    group_id              uuid NOT NULL REFERENCES masslook_groups(id) ON DELETE CASCADE,
    account_name          text,
    group_title           text,
    status                text DEFAULT 'pending',  -- pending | joined | failed | requested
    last_join_attempt_at  timestamptz,
    joined_at             timestamptz,
    error_message         text,
    created_at            timestamptz DEFAULT now(),
    updated_at            timestamptz DEFAULT now(),
    UNIQUE (account_id, group_id)
);

CREATE INDEX IF NOT EXISTS idx_masslook_account_groups_account ON masslook_account_groups(account_id);
CREATE INDEX IF NOT EXISTS idx_masslook_groups_active ON masslook_groups(is_active);

-- Extend story_views for group-based masslooking.
ALTER TABLE story_views ADD COLUMN IF NOT EXISTS group_id uuid REFERENCES masslook_groups(id) ON DELETE SET NULL;
ALTER TABLE story_views ADD COLUMN IF NOT EXISTS telegram_user_id bigint;
ALTER TABLE story_views ADD COLUMN IF NOT EXISTS liked_count integer DEFAULT 0;
ALTER TABLE story_views ALTER COLUMN target_id DROP NOT NULL;

ALTER TABLE account_settings ADD COLUMN IF NOT EXISTS masslook_participants_limit integer DEFAULT 500;
ALTER TABLE account_settings ADD COLUMN IF NOT EXISTS masslook_like_enabled boolean DEFAULT true;
ALTER TABLE account_settings ADD COLUMN IF NOT EXISTS story_reaction_emoji text DEFAULT '❤️';
