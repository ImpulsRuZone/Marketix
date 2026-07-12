-- Denormalized names for readable account_chats rows in Supabase UI.

ALTER TABLE account_chats ADD COLUMN IF NOT EXISTS account_name text;
ALTER TABLE account_chats ADD COLUMN IF NOT EXISTS chat_title text;

UPDATE account_chats ac
SET account_name = a.name
FROM accounts a
WHERE a.id = ac.account_id
  AND ac.account_name IS NULL
  AND a.name IS NOT NULL;

UPDATE account_chats ac
SET chat_title = tc.title
FROM target_chats tc
WHERE tc.id = ac.chat_id
  AND ac.chat_title IS NULL
  AND tc.title IS NOT NULL;
