-- Mass-looking (story viewing) tables and account settings.

-- Targets: users/channels whose stories we want to view.
CREATE TABLE IF NOT EXISTS story_targets (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    target_url   text NOT NULL UNIQUE,
    telegram_id  bigint,
    username     text,
    title        text,
    is_active    boolean DEFAULT true,
    created_at   timestamptz DEFAULT now(),
    updated_at   timestamptz DEFAULT now()
);

-- Log of viewed stories per account.
CREATE TABLE IF NOT EXISTS story_views (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    target_id       uuid REFERENCES story_targets(id) ON DELETE SET NULL,
    account_name    text,
    target_username text,
    target_title    text,
    stories_count   integer DEFAULT 0,
    max_story_id    integer,
    status          text DEFAULT 'viewed',  -- viewed | skipped | failed
    error_message   text,
    created_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_story_views_account ON story_views(account_id);
CREATE INDEX IF NOT EXISTS idx_story_views_created ON story_views(created_at);
CREATE INDEX IF NOT EXISTS idx_story_targets_active ON story_targets(is_active);

-- Per-account masslook settings.
ALTER TABLE account_settings ADD COLUMN IF NOT EXISTS masslook_enabled boolean DEFAULT false;
ALTER TABLE account_settings ADD COLUMN IF NOT EXISTS max_story_views_per_day integer DEFAULT 100;
ALTER TABLE account_settings ADD COLUMN IF NOT EXISTS story_view_delay_min_seconds integer DEFAULT 5;
ALTER TABLE account_settings ADD COLUMN IF NOT EXISTS story_view_delay_max_seconds integer DEFAULT 30;
ALTER TABLE account_settings ADD COLUMN IF NOT EXISTS masslook_cycle_pause_min_seconds integer DEFAULT 300;
ALTER TABLE account_settings ADD COLUMN IF NOT EXISTS masslook_cycle_pause_max_seconds integer DEFAULT 900;
