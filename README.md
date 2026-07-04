# Neurocomment — мультиаккаунтный Telegram-бот

Бот автоматически читает посты в Telegram-каналах и публикует AI-комментарии от лица нескольких аккаунтов параллельно.

## Структура проекта

```
.
├── app/
│   ├── __init__.py
│   ├── config.py           # Общие настройки + загрузка accounts.json
│   ├── ai.py               # Генерация комментариев через OpenAI
│   ├── db.py               # PostgreSQL (события, комментарии, каналы)
│   ├── channels_store.py   # Excel-лист на аккаунт + синхронизация с БД
│   ├── joiner.py           # Вступление в каналы
│   ├── account_bot.py      # Логика одного аккаунта
│   └── main.py             # Точка входа, запускает все аккаунты
├── data/
│   ├── channels_database.xlsx  # База каналов (лист = аккаунт)
│   └── sessions/               # Сессии Telethon
├── accounts.json.example
├── .env.example
├── requirements.txt
└── .gitignore
```

## Быстрый старт

### 1. Установить зависимости

```bash
pip install -r requirements.txt
```

### 2. Настроить окружение

```bash
cp .env.example .env
# Заполнить OPENAI_API_KEY, DATABASE_URL и прочее
```

### 3. Создать список аккаунтов

```bash
cp accounts.json.example accounts.json
# Заполнить api_id, api_hash, phone для каждого аккаунта
```

`api_id` и `api_hash` — на [my.telegram.org](https://my.telegram.org).

### 4. Создать листы каналов для аккаунтов

```bash
python -m app.channels_store
```

Создаётся файл `data/channels_database.xlsx`:
- лист `_инструкция` — как пользоваться
- **отдельный лист на каждый аккаунт** из `accounts.json`

### 5. Заполнить каналы в Excel

Откройте `data/channels_database.xlsx` → лист аккаунта (например `account1`):

| Канал | Приоритет | Активен | Заметка |
|-------|-----------|---------|---------|
| @girl_humor | Высокий | да | |
| @meow_meow_cute | Средний | да | |
| @topor | Низкий | нет | политика |

- **Канал** — `@username`, `username` или invite-ссылка `https://t.me/+...`
- **Приоритет** — `Высокий` / `Средний` / `Низкий`
- **Активен** — `да` / `нет` (неактивные не вступают и не комментируют)

### 6. Синхронизировать и запустить

```bash
python -m app.channels_store   # импорт Excel → PostgreSQL
python -m app.main             # запуск бота
```

При запуске `python -m app.main` синхронизация выполняется автоматически.

## Добавление нового аккаунта

1. Добавьте блок в `accounts.json`:
```json
{
  "name": "account3",
  "api_id": 123456,
  "api_hash": "your_hash",
  "phone": "+79009999999"
}
```

2. Создайте лист для него:
```bash
python -m app.channels_store
```

3. В Excel появится **новый лист `account3`** — заполните каналы.

4. Перезапустите бота:
```bash
sudo systemctl restart neurocomment
```

## Откуда бот берёт каналы

Приоритет источников:

1. **PostgreSQL** (`account_channels`) — если задан `DATABASE_URL`
2. **Excel** (`data/channels_database.xlsx`, лист аккаунта)
3. Старый формат `channels` в `accounts.json` (импортируется в Excel при первой синхронизации)
4. Глобальный список `MY_CHANNELS` в `app/joiner.py`

## База данных PostgreSQL

Таблицы создаются автоматически при первом запуске.

| Таблица | Назначение |
|---------|------------|
| `events` | Системные события |
| `comments` | Отправленные комментарии |
| `bot_accounts` | Зарегистрированные аккаунты |
| `account_channels` | Каналы для вступления и комментинга по аккаунтам |

## Мультиаккаунт

Каждый аккаунт работает независимо:

- свой session-файл (`data/sessions/<name>.session`)
- **свой лист** в `channels_database.xlsx`
- **свои записи** в `account_channels`
- параллельная работа через `asyncio.gather`

## Без PostgreSQL

Если `DATABASE_URL` не задан, бот читает каналы **напрямую из Excel**.
Команда `python -m app.channels_store` всё равно создаёт/обновляет листы.
