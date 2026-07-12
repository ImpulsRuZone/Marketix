-- Fix account_chats.status check constraint
-- Run in Supabase SQL Editor

ALTER TABLE account_chats DROP CONSTRAINT IF EXISTS account_chats_status_check;

UPDATE account_chats SET status = lower(status) WHERE status IS NOT NULL;

ALTER TABLE account_chats ADD CONSTRAINT account_chats_status_check
    CHECK (status IN ('pending', 'joined', 'failed', 'requested'));
