-- Allow 'excluded' status for channels removed from monitoring due to access errors.

ALTER TABLE account_chats DROP CONSTRAINT IF EXISTS account_chats_status_check;

ALTER TABLE account_chats ADD CONSTRAINT account_chats_status_check
    CHECK (status IN ('pending', 'joined', 'failed', 'requested', 'excluded'));
