-- Run in Supabase SQL Editor if the bot reports missing columns
-- Safe to run multiple times (IF NOT EXISTS / IF EXISTS)

ALTER TABLE target_chats ADD COLUMN IF NOT EXISTS username text;
ALTER TABLE target_chats ADD COLUMN IF NOT EXISTS title text;
ALTER TABLE target_chats ADD COLUMN IF NOT EXISTS type text;

-- payload may have been created as NOT NULL in some setups
ALTER TABLE logs ALTER COLUMN payload DROP NOT NULL;
