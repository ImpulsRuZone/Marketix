-- Sleep window uses Moscow time by default.
ALTER TABLE account_settings
    ALTER COLUMN timezone SET DEFAULT 'Europe/Moscow';

UPDATE account_settings
SET timezone = 'Europe/Moscow',
    updated_at = now()
WHERE timezone IS NULL
   OR timezone = ''
   OR timezone = 'UTC';
