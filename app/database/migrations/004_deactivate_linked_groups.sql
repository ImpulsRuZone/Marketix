-- Linked discussion groups are auto-created with chat_url = 'id:TELEGRAM_ID'.
-- They must not be joined or monitored as separate targets.

UPDATE target_chats
SET is_active = false
WHERE chat_url LIKE 'id:%';
