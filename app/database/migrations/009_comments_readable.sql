-- Human-readable comment fields + view for Supabase Table Editor.

ALTER TABLE comments ADD COLUMN IF NOT EXISTS account_name text;
ALTER TABLE comments ADD COLUMN IF NOT EXISTS chat_title text;

UPDATE comments c
SET account_name = a.name
FROM accounts a
WHERE c.account_id = a.id
  AND c.account_name IS NULL;

UPDATE comments c
SET chat_title = tc.title
FROM target_chats tc
WHERE c.chat_id = tc.id
  AND c.chat_title IS NULL;

CREATE OR REPLACE VIEW comments_readable AS
SELECT
    to_char(
        c.sent_at AT TIME ZONE 'Europe/Moscow',
        'DD.MM.YYYY HH24:MI:SS'
    ) AS sent_at_moscow,
    COALESCE(c.account_name, a.name) AS account_name,
    COALESCE(c.chat_title, tc.title) AS chat_title,
    c.post_text,
    c.generated_comment,
    c.status,
    c.sent_comment
FROM comments c
LEFT JOIN accounts a ON a.id = c.account_id
LEFT JOIN target_chats tc ON tc.id = c.chat_id
ORDER BY c.sent_at DESC NULLS LAST, c.created_at DESC;
