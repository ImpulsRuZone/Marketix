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
nano .env   # вставить DATABASE_URL, API_ID, API_HASH, OPENAI_API_KEY
```

`API_ID` и `API_HASH` получаются один раз на [my.telegram.org](https://my.telegram.org) и используются для **всех** аккаунтов.

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
- Использовать proxy? (тип, host, port, логин/пароль)
- GPT prompt для этого аккаунта
- Номер телефона
- SMS-код / пароль 2FA

`API_ID` / `API_HASH` берутся из `.env` автоматически — вводить не нужно.

После авторизации `session_string` сохраняется в Supabase — файлы сессии не нужны.

### 5. Добавить каналы для слежения

Список каналов хранится в таблице `target_chats`. Актуальная база авто/мото-каналов лежит в `seeds/channels/` (188 каналов).

**Обновить каналы в Supabase (заменить старый список):**

```bash
# Вариант 1: SQL-миграция в Supabase SQL Editor
# app/database/migrations/011_replace_target_chats.sql

# Вариант 2: скрипт (нужен DATABASE_URL в .env)
python3 scripts/import_channels_from_csv.py

# Проверка без записи в БД
python3 scripts/import_channels_from_csv.py --dry-run
```

После обновления перезапустите бота с `--join`, чтобы аккаунты вступили в новые каналы:

```bash
python3 -m app.main --join
```

Вручную добавить один канал:

```sql
INSERT INTO target_chats (chat_url) VALUES ('@moscow');
```

### 6. Запустить бота

```bash
python3 -m app.main
```

При запуске в терминале бот спросит:

```
Вступать в новые каналы из списка target_chats?
  1) Да — вступить в каналы, где аккаунт ещё не состоит
  2) Нет — только слушать посты (без новых вступлений)
```

Флаги командной строки:

```bash
python3 -m app.main --join      # сразу вступать в новые каналы
python3 -m app.main --no-join   # не вступать, только комментировать
```

Для systemd (без интерактива) в `.env`:

```env
JOIN_ON_STARTUP=false   # по умолчанию — не вступать при рестарте
JOIN_ON_STARTUP=true    # вступать в новые каналы при каждом рестарте
```

### Или через systemd (VPS)

Установка и автозапуск при перезагрузке сервера:

```bash
cd ~/neurocomment
git pull origin cursor/full-architecture-bot-7336
pip3 install -r requirements.txt
sudo bash deploy/install-systemd.sh
```

Управление сервисом:

```bash
systemctl status neurocomment      # статус
journalctl -u neurocomment -f        # логи в реальном времени
systemctl restart neurocomment     # перезапуск после git pull
systemctl stop neurocomment        # остановить
systemctl disable neurocomment     # убрать из автозагрузки
```

Файл unit: `deploy/neurocomment.service`. Скрипт `deploy/install-systemd.sh` подставляет путь к проекту и пользователя автоматически, а также добавляет `JOIN_ON_STARTUP=false` в `.env`, если переменной ещё нет.

Если `.env` создан раньше — добавьте вручную:

```env
# true — вступать в новые каналы при рестарте; false — только слушать посты
JOIN_ON_STARTUP=false
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
        ├── join_manager: вступить во все target_chats (если включено при старте)
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
| `target_chats` | Целевые каналы (см. `seeds/channels/target_channels.txt`) |
| `account_chats` | Статус вступления аккаунта в канал |
| `posts` | Найденные посты |
| `comments` | Сгенерированные и отправленные комментарии |
| `logs` | Системные события |

## Таблица нейрокомментинга

В Supabase удобно смотреть представление **`comments_readable`** — без UUID, время отправки в Москве:

| Колонка | Описание |
|---------|----------|
| `sent_at_moscow` | Время отправки (МСК) |
| `account_name` | Имя аккаунта |
| `chat_title` | Название канала |
| `post_text` | Текст поста |
| `generated_comment` | Сгенерированный GPT комментарий |
| `status` | `sent` / `failed` / `generated` |
| `sent_comment` | Фактически отправленный текст |

Экспорт из Supabase (Table Editor → Export → SQL) можно превратить в CSV для Excel / Google Sheets:

```bash
python3 scripts/sql_comments_to_csv.py exports/neurocommenting/comments_rows.sql
```

Результат: `exports/neurocommenting/neurocommenting_table.csv`.

Текущий снимок (422 записи, июнь–июль 2026):

| Показатель | Значение |
|------------|----------|
| Отправлено | 267 |
| Ошибка | 153 |
| Сгенерировано (не отправлено) | 2 |
| Аккаунты | «Аккаунд с Апи Айди» (290), +77086215613 (132) |
