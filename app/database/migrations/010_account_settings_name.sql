-- Readable account name in account_settings + backfill missing rows.

ALTER TABLE account_settings ADD COLUMN IF NOT EXISTS account_name text;

UPDATE account_settings s
SET account_name = a.name
FROM accounts a
WHERE s.account_id::uuid = a.id
  AND (s.account_name IS NULL OR s.account_name = '');

INSERT INTO account_settings (account_id, account_name)
SELECT a.id, a.name
FROM accounts a
WHERE NOT EXISTS (
    SELECT 1 FROM account_settings s WHERE s.account_id::uuid = a.id
);
