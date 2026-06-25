# Multi-account Telegram Comment Bot Architecture

## Core decisions

1. **Python + Telethon + Supabase + OpenAI API**
2. **No proxy table**: proxy settings are kept per account in `accounts`.
3. **Single shared tables with `account_id`** instead of one table per account.
4. **Interactive onboarding** with strict login flow:
   - phone number
   - proxy choice (yes/no) before connection
   - `api_id` + `api_hash`
   - manual SMS/Telegram confirmation code
   - optional Telegram 2FA password
5. **Per-account settings**:
   - prompt
   - daily comment percent
   - max comments per day
   - sleep window
   - join delay range
   - comment delay range

## Runtime architecture

- `app/main.py`
  - `onboard`: create and configure an account
  - `run-workers`: run all active accounts concurrently
- `app/telegram/account_worker.py`
  - one Telethon client per account
  - receives new messages/posts
  - checks sleep/limits/percent
  - generates comment
  - sends comment with randomized delay
- `app/telegram/join_manager.py`
  - joins configured groups/chats
  - uses per-account delay range for safer pacing
- `app/comments/generator.py`
  - combines account prompt + post text
  - generates one response through OpenAI API
- `app/logs/logger.py`
  - writes both console logs and Supabase logs

## Notes on safety

- This template supports controlled automation for legitimate channels/chats where you have permission.
- Keep conservative limits and sleep windows enabled for every account.
- Start with low comment percentages and low max/day values, then tune gradually.
