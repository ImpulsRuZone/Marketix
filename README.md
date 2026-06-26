# Neurocomment Bot

Мультиаккаунтный Telegram-бот, который читает посты в каналах и публикует AI-комментарии от лица нескольких аккаунтов параллельно.

## Стек

- **Python 3.11+**
- **Telethon** — работа с Telegram-аккаунтами
- **Supabase / PostgreSQL** — база данных, логи, настройки
- **OpenAI API** — генерация комментариев через GPT-4o-mini
- **asyncio** — параллельная работа аккаунтов
- **Docker** — деплой

## Структура проекта

```
app/
├── main.py                        # Точка входа
├── config.py                      # Переменные окружения
│
├── telegram/
│   ├── account_login.py           # CLI: добавление аккаунта
│   ├── client_factory.py          # Создание Telethon client
│   ├── account_worker.py          # Worker одного аккаунта
│   ├── join_manager.py            # Вступление в каналы
│   └── post_listener.py           # Регистрация обработчика постов
│
├── settings/
│   └── settings_manager.py        # Настройки лимитов и сна
│
├── comments/
│   ├── generator.py               # Генерация через GPT
│   ├── comment_scheduler.py       # Решение: комментировать или нет
│   └── comment_sender.py          # Отправка комментария
│
├── database/
│   ├── supabase_client.py         # asyncpg connection pool
│   ├── repositories.py            # Все SQL-запросы
│   └── schema.sql                 # Схема БД
│
├── logs/
│   └── logger.py                  # Логирование в stdout + DB
│
└── utils/
    ├── time_utils.py              # Логика окна сна
    ├── proxy_utils.py             # Построение proxy-tuple
    └── random_utils.py            # Случайные задержки
```

## Быстрый старт

### 1. Клонировать и установить зависимости

```bash
git clone https://github.com/ImpulsRuZone/Marketix.git neurocomment
cd neurocomment
pip3 install -r requirements.txt
```

### 2. Настроить окружение

```bash
cp .env.example .env
nano .env   # вставить DATABASE_URL и OPENAI_API_KEY
```

### 3. Применить схему БД

```bash
psql $DATABASE_URL -f app/database/schema.sql
```

Или в Supabase: **SQL Editor** → вставить содержимое `schema.sql` → Run.

### 4. Добавить Telegram-аккаунт (интерактивно)

```bash
python3 -m app.telegram.account_login
```

Скрипт спросит:
- Название аккаунта
- Номер телефона
- Использовать proxy?
- `api_id` / `api_hash` (с [my.telegram.org](https://my.telegram.org))
- GPT prompt для этого аккаунта
- SMS-код / пароль 2FA

После авторизации `session_string` сохраняется в Supabase — файлы сессии не нужны.

### 5. Добавить каналы для слежения

В таблице `target_chats` добавить каналы:

```sql
INSERT INTO target_chats (chat_url) VALUES
  ('@moscow'),
  ('@rozetked'),
  ('@nexta_live');
```

### 6. Запустить бота

```bash
python3 -m app.main
```

### Или через Docker

```bash
# Первый раз: добавить аккаунт интерактивно
docker compose run --rm bot python -m app.telegram.account_login

# Запустить бота
docker compose up -d
```

## Настройки аккаунта

В таблице `account_settings` можно изменить:

| Поле | По умолчанию | Описание |
|------|-------------|----------|
| `daily_comment_percent` | 30 | % постов, на которые реагируем |
| `max_comments_per_day` | 20 | Максимум комментариев в день |
| `sleep_start_time` | null | Начало "сна" (например `23:00`) |
| `sleep_end_time` | null | Конец "сна" (например `08:00`) |
| `timezone` | UTC | Временная зона (например `Europe/Moscow`) |
| `join_delay_min_seconds` | 120 | Мин. задержка между вступлениями |
| `join_delay_max_seconds` | 600 | Макс. задержка между вступлениями |
| `is_active` | true | Вкл/выкл аккаунт без удаления |

## Логика работы

```
main.py
  └── для каждого active аккаунта → AccountWorker.run()
        ├── client_factory: создать TelegramClient (StringSession из БД)
        ├── проверить окно сна → если спим, ждать
        ├── join_manager: вступить во все target_chats
        ├── post_listener: зарегистрировать обработчик NewMessage
        └── при новом посте:
              ├── comment_scheduler: комментировать? (% + лимит)
              ├── случайная задержка 60–300 сек
              ├── generator: GPT → комментарий
              └── comment_sender: отправить в linked group
```

## Таблицы БД

| Таблица | Описание |
|---------|----------|
| `accounts` | Telegram-аккаунты (session, proxy, prompt) |
| `account_settings` | Настройки лимитов и сна |
| `target_chats` | Целевые каналы |
| `account_chats` | Статус вступления аккаунта в канал |
| `posts` | Найденные посты |
| `comments` | Сгенерированные и отправленные комментарии |
| `logs` | Системные события |
