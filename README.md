# Multi-account Telegram Comment Bot (Python + Telethon + Supabase)

Каркас проекта для мультиаккаунтного Telegram-бота с:

- отдельными настройками на каждый аккаунт;
- обязательным шагом выбора прокси перед подключением;
- ручным вводом кода подтверждения Telegram;
- настройкой лимитов, сна и задержек;
- логированием и хранением комментариев в Supabase.

## Стек

- Python 3.10+
- Telethon
- Supabase
- OpenAI API

## Структура

```text
app/
  main.py
  config.py
  comments/
  db/
  logs/
  settings/
  telegram/
docs/
  ARCHITECTURE.md
```

## 1) Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 2) Переменные окружения

Создайте `.env`:

```env
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
```

## 3) Создание таблиц Supabase

Выполните SQL из файла:

`app/db/schema.sql`

## 4) Онбординг аккаунта

```bash
python3 -m app.main onboard
```

Во время onboarding ввод идет в нужном порядке:

1. Номер телефона
2. Использовать прокси или нет
3. API ID / API hash
4. Код подтверждения Telegram (вручную)
5. Пароль 2FA (если включен)
6. Настройки аккаунта (daily percent, max/day, sleep, delays, prompt)
7. Группы/чаты для работы

Все интерактивные вопросы onboarding выводятся на русском языке.
Если код не пришел, введите `resend` (или `/resend`) для повторной отправки, либо `sms` (или `/sms`) для попытки доставки по SMS.

## 5) Запуск воркеров

```bash
python3 -m app.main run-workers
```

Будет поднят отдельный Telethon-клиент для каждого активного аккаунта.

## Важно

Используйте только в легитимных сценариях (свои/разрешенные чаты и каналы), с аккуратными лимитами и аудитом.

## Troubleshooting

### UnicodeDecodeError при вводе prompt на русском

Если видите ошибку `UnicodeDecodeError` при вводе текста на кириллице:

1. Убедитесь, что у вас свежая версия кода (в этом проекте уже есть fallback-декодирование ввода).
2. На VPS выставьте UTF-8 locale перед запуском:

```bash
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
```
