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

1. Имя аккаунта
2. Промпт аккаунта
3. Номер телефона
4. API ID / API hash
5. Прокси: да/нет
6. Код подтверждения Telegram (вручную)
7. Пароль 2FA (если включен)
8. Настройки аккаунта (daily percent, max/day, sleep, delays)
9. Группы/чаты для работы

Все интерактивные вопросы onboarding выводятся на русском языке.
Авторизация выполняется через встроенный режим `Telethon.start()` (как в классическом рабочем сценарии с файловой сессией).

## 5) Запуск воркеров

```bash
python3 -m app.main run-workers
```

Будет поднят отдельный Telethon-клиент для каждого активного аккаунта.
Обработка постов выполнена в стиле классического Telethon-хэндлера:

- слушаются только целевые каналы аккаунта;
- учитываются только посты каналов (`message.post`);
- короткие посты пропускаются;
- комментарий отправляется в linked-группу канала;
- при `MsgIdInvalidError` используется fallback-поиск поста в linked-группе.

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

### Код авторизации Telegram не приходит

1. Убедитесь, что вход без прокси.
2. Проверяйте сервисный чат `Telegram` и архив чатов в официальном приложении.
3. Не отправляйте много запросов подряд — Telegram может ограничить выдачу кода.
4. Если видите `PhoneNumberFloodError` или `SendCodeUnavailableError`, подождите 5-15 минут и повторите onboarding.
