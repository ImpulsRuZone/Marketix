-- Run in Supabase SQL Editor (safe to run multiple times)

ALTER TABLE target_chats ADD COLUMN IF NOT EXISTS username text;
ALTER TABLE target_chats ADD COLUMN IF NOT EXISTS title text;
ALTER TABLE target_chats ADD COLUMN IF NOT EXISTS type text;
ALTER TABLE target_chats ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

ALTER TABLE account_chats ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

ALTER TABLE logs ALTER COLUMN payload DROP NOT NULL;

UPDATE logs SET level = lower(level) WHERE level IS NOT NULL;

-- Normalize logs.level check to accept lowercase values
ALTER TABLE logs DROP CONSTRAINT IF EXISTS logs_level_check;
-- Fix target_chats.chat_id type if created as text
ALTER TABLE target_chats
    ALTER COLUMN chat_id TYPE bigint
    USING NULLIF(chat_id::text, '')::bigint;
