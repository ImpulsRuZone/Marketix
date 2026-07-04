# Neurocomment — мультиаккаунтный Telegram-бот

Бот автоматически читает посты в Telegram-каналах и публикует AI-комментарии от лица нескольких аккаунтов параллельно.

## Структура проекта

```
.
├── app/
│   ├── config.py           # Настройки + accounts.json
│   ├── channels_store.py   # Списки каналов (txt на аккаунт)
│   ├── account_bot.py      # Логика одного аккаунта
│   ├── joiner.py           # Вступление в каналы
│   ├── db.py               # PostgreSQL
│   └── main.py             # Запуск
├── data/
│   ├── channels/           # Один .txt файл на аккаунт
│   │   ├── account1.txt
│   │   └── account2.txt
│   └── sessions/           # Сессии Telethon
├── accounts.json
└── .env
```

## Быстрый старт

```bash
pip install -r requirements.txt
cp .env.example .env          # заполнить OPENAI_API_KEY
cp accounts.json.example accounts.json   # заполнить аккаунты
python -m app.channels_store  # создать txt-файлы для аккаунтов
# отредактировать data/channels/account1.txt
python -m app.main
```

## Как добавить каналы для аккаунта

Откройте файл `data/channels/<имя_аккаунта>.txt` и впишите каналы — **один на строку**:

```text
@girl_humor
@meow_meow_cute
@official_romanceclub
https://t.me/+InviteHashHere
```

Строки с `#` — комментарии, игнорируются.

Перезапустите бота — он подхватит список автоматически.

## Как добавить новый аккаунт

**1.** Добавьте в `accounts.json`:

```json
{
  "name": "account3",
  "api_id": 123456,
  "api_hash": "ваш_hash",
  "phone": "+79009999999"
}
```

**2.** Создайте файл каналов:

```bash
python -m app.channels_store
```

Появится `data/channels/account3.txt`

**3.** Впишите каналы в этот файл (по одному на строку)

**4.** Перезапустите:

```bash
sudo systemctl restart neurocomment
```

## Откуда бот берёт каналы

1. `data/channels/<имя>.txt` — основной способ
2. Поле `channels` в `accounts.json` (если txt пустой)
3. Общий список `MY_CHANNELS` в `app/joiner.py` (запасной)

## База данных

Если задан `DATABASE_URL`, каналы из txt синхронизируются в таблицу `account_channels` при запуске.  
Редактировать нужно только txt-файл — не БД и не Excel.
