#!/usr/bin/env python3
"""Generate Neurocomment Bot architecture PDF (Russian)."""

from pathlib import Path

from fpdf import FPDF

FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "neurocomment-architecture.pdf"


class ArchPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font("DejaVu", "", FONT_REGULAR)
        self.add_font("DejaVu", "B", FONT_BOLD)
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(15, 15, 15)
        self.set_right_margin(15)

    def header(self):
        if self.page_no() > 1:
            self.set_font("DejaVu", "", 9)
            self.set_text_color(120, 120, 120)
            self.cell(0, 8, "Neurocomment Bot — Архитектура", align="R", new_x="LMARGIN", new_y="NEXT")
            self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVu", "", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Страница {self.page_no()}/{{nb}}", align="C")

    def title_page(self):
        self.add_page()
        self.ln(40)
        self.set_font("DejaVu", "B", 28)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 14, "Neurocomment Bot", align="C")
        self.ln(6)
        self.set_font("DejaVu", "", 16)
        self.set_text_color(80, 80, 80)
        self.multi_cell(0, 10, "Архитектура мультиаккаунтного\nTelegram-бота для AI-комментирования", align="C")
        self.ln(20)
        self.set_font("DejaVu", "", 11)
        self.multi_cell(0, 7, "Репозиторий: github.com/ImpulsRuZone/Marketix\nВетка: cursor/full-architecture-bot-7336", align="C")

    def h1(self, text: str):
        self.ln(4)
        self.set_font("DejaVu", "B", 16)
        self.set_text_color(20, 60, 120)
        self.multi_cell(0, 10, text)
        self.ln(2)

    def h2(self, text: str):
        self.ln(3)
        self.set_font("DejaVu", "B", 13)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 8, text)
        self.ln(1)

    def h3(self, text: str):
        self.ln(2)
        self.set_font("DejaVu", "B", 11)
        self.set_text_color(60, 60, 60)
        self.multi_cell(0, 7, text)
        self.ln(1)

    def body(self, text: str):
        self.set_x(self.l_margin)
        self.set_font("DejaVu", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 6, text)
        self.ln(1)

    def bullet(self, text: str):
        self.set_x(self.l_margin)
        self.set_font("DejaVu", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 6, f"- {text}")

    def code_block(self, text: str):
        self.set_fill_color(245, 245, 245)
        self.set_font("DejaVu", "", 9)
        self.set_text_color(50, 50, 50)
        for line in text.split("\n"):
            self.cell(0, 5, f"  {line}", new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(2)

    def table(self, headers: list[str], rows: list[list[str]], col_widths: list[int] | None = None):
        self.set_x(self.l_margin)
        if col_widths is None:
            w = int(self.epw // len(headers))
            col_widths = [w] * len(headers)
        else:
            total = sum(col_widths)
            scale = self.epw / total
            col_widths = [int(w * scale) for w in col_widths]

        self.set_font("DejaVu", "B", 9)
        self.set_fill_color(230, 240, 250)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 7, h, border=1, fill=True)
        self.ln()

        self.set_font("DejaVu", "", 9)
        fill = False
        for row in rows:
            self.set_x(self.l_margin)
            self.set_fill_color(250, 250, 250) if fill else self.set_fill_color(255, 255, 255)
            for i, cell in enumerate(row):
                txt = cell if len(cell) <= 80 else cell[:77] + "..."
                self.cell(col_widths[i], 7, txt, border=1, fill=fill)
            self.ln()
            fill = not fill
        self.ln(3)


def build_pdf() -> Path:
    pdf = ArchPDF()
    pdf.alias_nb_pages()
    pdf.title_page()

    pdf.add_page()
    pdf.h1("1. Общая идея")
    pdf.body(
        "Neurocomment Bot — мультиаккаунтный Telegram-комментатор. Несколько Telegram-аккаунтов "
        "работают параллельно, каждый слушает целевые каналы. При появлении нового поста бот "
        "решает — комментировать или нет, генерирует текст через GPT-4o-mini и публикует "
        "комментарий в linked-группу канала. Все данные хранятся в Supabase/PostgreSQL."
    )

    pdf.h2("Стек технологий")
    pdf.table(
        ["Компонент", "Технология"],
        [
            ["Telegram API", "Telethon (StringSession)"],
            ["AI", "OpenAI GPT-4o-mini"],
            ["БД", "PostgreSQL / Supabase (asyncpg)"],
            ["Параллелизм", "asyncio"],
            ["Деплой", "Docker, systemd"],
        ],
        [60, 130],
    )

    pdf.h1("2. Высокоуровневая схема")
    pdf.code_block(
        "main.py\n"
        "  └── asyncio.gather(AccountWorker × N)\n"
        "        ├── Telethon Client (StringSession из БД)\n"
        "        ├── post_listener → NewMessage handler\n"
        "        ├── join_manager → вступление в каналы (фон)\n"
        "        └── при новом посте:\n"
        "              ├── comment_scheduler (лимит + % + сон)\n"
        "              ├── random delay 60–300 сек\n"
        "              ├── generator → GPT-4o-mini\n"
        "              └── comment_sender → linked-группа"
    )

    pdf.h1("3. Точка входа — main.py")
    pdf.body("При запуске бот выполняет следующие шаги:")
    for step in [
        "Читает .env (DATABASE_URL, API_ID, API_HASH, OPENAI_API_KEY)",
        "Инициализирует пул соединений с БД (asyncpg)",
        "Синхронизирует account_settings для всех аккаунтов",
        "Загружает активные аккаунты из таблицы accounts",
        "Создаёт по одному AccountWorker на каждый аккаунт",
        "Запускает все воркеры через asyncio.gather() — полностью параллельно",
    ]:
        pdf.bullet(step)

    pdf.h3("Режим вступления в каналы")
    pdf.table(
        ["Флаг / переменная", "Поведение"],
        [
            ["--join", "Вступать в новые каналы при старте"],
            ["--no-join", "Только слушать уже известные каналы"],
            ["JOIN_ON_STARTUP=true", "Для systemd: вступать при рестарте"],
            ["JOIN_ON_STARTUP=false", "Для systemd: не вступать (по умолчанию)"],
        ],
        [55, 135],
    )

    pdf.h1("4. Воркер аккаунта — AccountWorker")
    pdf.body(
        "Центральный компонент. Один экземпляр = один Telegram-аккаунт. "
        "При сбое воркер автоматически перезапускается через 30 секунд."
    )

    pdf.h2("Жизненный цикл при старте")
    for step in [
        "get_settings() — загрузка настроек из БД",
        "client.connect() — подключение Telethon",
        "is_user_authorized() — проверка сессии",
        "_wait_if_sleeping() — ожидание окончания окна сна",
        "get_joinable_target_chats() — список целевых каналов",
        "resolve_monitored_ids() — ID каналов для прослушивания",
        "register_post_handler() — регистрация обработчика постов",
        "join_all_chats() в фоне (если join_on_startup=true)",
        "run_until_disconnected() — основной цикл",
    ]:
        pdf.bullet(step)

    pdf.body(
        "Важно: прослушивание постов начинается сразу, вступление в новые каналы "
        "идёт в фоне — бот не ждёт окончания join перед комментированием."
    )

    pdf.h2("Обработка нового поста")
    for step in [
        "Обновляет настройки из БД (можно менять лимиты без перезапуска)",
        "Проверяет is_active — аккаунт включён?",
        "Проверяет окно сна (sleep_start_time / sleep_end_time + timezone)",
        "Планировщик — комментировать или пропустить?",
        "Случайная задержка 60–300 сек (имитация человека)",
        "Сохраняет пост в БД (target_chats + posts)",
        "GPT генерирует комментарий",
        "Отправляет комментарий в linked-группу",
        "При ошибке доступа — исключает канал из мониторинга для этого аккаунта",
    ]:
        pdf.bullet(step)

    pdf.h1("5. Модули Telegram")

    pdf.h2("client_factory.py")
    pdf.body("Создаёт TelegramClient из записи в БД:")
    pdf.bullet("Сессия — StringSession (хранится в БД, не на диске)")
    pdf.bullet("API_ID / API_HASH — общие для всех аккаунтов из .env")
    pdf.bullet("Опционально — proxy (SOCKS5/HTTP) per account")

    pdf.h2("post_listener.py")
    pdf.body("Регистрирует обработчик events.NewMessage с фильтрами:")
    pdf.bullet("Только каналы (event.is_channel)")
    pdf.bullet("Только из monitored_ids")
    pdf.bullet("Только посты (event.message.post)")
    pdf.bullet("Только текст ≥ 50 символов (MIN_POST_LENGTH)")

    pdf.h2("join_manager.py")
    pdf.body("Вступление в каналы:")
    pdf.bullet("Берёт список target_chats из БД")
    pdf.bullet("Пропускает уже joined и excluded")
    pdf.bullet("Вступает в канал + его linked-группу (для комментариев)")
    pdf.bullet("Записывает статус в account_chats (pending → joined / failed / excluded)")
    pdf.bullet("Случайная задержка между вступлениями (120–600 сек по умолчанию)")

    pdf.h1("6. Пайплайн комментариев")

    pdf.h2("comment_scheduler.py — решение «комментировать?»")
    pdf.bullet("Если сегодня уже отправлено ≥ max_comments_per_day → пропуск")
    pdf.bullet("Случайный бросок: комментировать с вероятностью daily_comment_percent / 100 (по умолчанию 30%)")

    pdf.h2("generator.py — генерация текста")
    pdf.code_block(
        "Модель: GPT-4o-mini, temperature=0.9\n"
        "system_prompt = account.gpt_prompt or DEFAULT_GPT_PROMPT\n"
        "user_message = post_text[:1000]\n"
        "Результат обрезается до MAX_COMMENT_LENGTH (200 символов)"
    )
    pdf.body("У каждого аккаунта может быть свой GPT prompt в таблице accounts.gpt_prompt.")

    pdf.h2("comment_sender.py — отправка")
    pdf.body(
        "Telegram не позволяет комментировать напрямую в канал — комментарий идёт "
        "в linked discussion group. Алгоритм отправки:"
    )
    for step in [
        "GetFullChannelRequest → получить linked_chat_id",
        "Сохранить запись в comments (status=generated)",
        "JoinChannelRequest в linked-группу",
        "Попытка 1: event.respond()",
        "Попытка 2: send_message(comment_to=msg_id)",
        "Fallback: GetDiscussionMessageRequest → reply в linked-группе",
        "Fallback: скан linked-группы (100 msg) → reply на forwarded post",
        "При успехе: status=sent; при ошибке: status=failed",
    ]:
        pdf.bullet(step)
    pdf.body("Принцип: отправка в Telegram независима от БД — запись в БД best-effort, не блокирует отправку.")

    pdf.h1("7. База данных")

    pdf.h2("Таблицы")
    pdf.table(
        ["Таблица", "Назначение"],
        [
            ["accounts", "Telegram-аккаунты (session, proxy, gpt_prompt)"],
            ["account_settings", "Лимиты, окно сна, timezone, is_active"],
            ["target_chats", "Целевые каналы (@username или URL)"],
            ["account_chats", "Статус вступления аккаунта в канал (M:N)"],
            ["posts", "Найденные посты в каналах"],
            ["comments", "Сгенерированные и отправленные комментарии"],
            ["logs", "Системные события (INFO / WARNING / ERROR)"],
        ],
        [45, 145],
    )

    pdf.h2("Представление comments_readable")
    pdf.body(
        "Удобная таблица для Supabase UI — без UUID, время в Москве, "
        "читаемые имена аккаунтов и каналов."
    )
    pdf.table(
        ["Колонка", "Описание"],
        [
            ["sent_at_moscow", "Время отправки (МСК)"],
            ["account_name", "Имя аккаунта"],
            ["chat_title", "Название канала"],
            ["post_text", "Текст поста"],
            ["generated_comment", "Сгенерированный GPT комментарий"],
            ["status", "sent / failed / generated"],
            ["sent_comment", "Фактически отправленный текст"],
        ],
        [50, 140],
    )

    pdf.h1("8. Настройки per account")
    pdf.body("В account_settings (можно менять в Supabase без перезапуска):")
    pdf.table(
        ["Параметр", "По умолчанию", "Назначение"],
        [
            ["daily_comment_percent", "30", "% постов, на которые реагируем"],
            ["max_comments_per_day", "20", "Жёсткий лимит в день"],
            ["sleep_start_time", "null", "Начало «сна» (например 23:00)"],
            ["sleep_end_time", "null", "Конец «сна» (например 08:00)"],
            ["timezone", "UTC", "Часовой пояс для сна"],
            ["join_delay_min/max", "120 / 600", "Задержка между вступлениями (сек)"],
            ["is_active", "true", "Вкл/выкл аккаунт"],
        ],
        [55, 35, 100],
    )

    pdf.h1("9. Обработка ошибок")

    pdf.h2("Автоисключение каналов")
    pdf.body("При ошибках доступа канал исключается из мониторинга для аккаунта:")
    pdf.bullet("private and you lack permission")
    pdf.bullet("chat_write_forbidden")
    pdf.bullet("you were banned")
    pdf.body("Статус excluded в account_chats — бот больше не тратит ресурсы на этот канал.")

    pdf.h2("Перезапуск воркера")
    pdf.body("При необработанном исключении воркер перезапускается через 30 сек (цикл while True в run()).")

    pdf.h1("10. Добавление аккаунта")
    pdf.code_block("python3 -m app.telegram.account_login")
    pdf.body("Интерактивный CLI:")
    for step in [
        "Имя аккаунта",
        "Proxy (опционально)",
        "GPT prompt",
        "Телефон → SMS-код → 2FA",
        "session_string сохраняется в БД",
    ]:
        pdf.bullet(step)

    pdf.h1("11. Деплой")
    pdf.bullet("Docker — docker compose up -d")
    pdf.bullet("systemd — deploy/neurocomment.service + deploy/install-systemd.sh")
    pdf.bullet("Логи — stdout + таблица logs в БД")

    pdf.h1("12. Поток данных (итог)")
    pdf.code_block(
        "Новый пост в канале\n"
        "    ↓\n"
        "post_listener (фильтр: канал, длина текста)\n"
        "    ↓\n"
        "comment_scheduler (лимит + % + сон)\n"
        "    ↓\n"
        "random delay 60–300 сек\n"
        "    ↓\n"
        "generator → GPT-4o-mini → комментарий\n"
        "    ↓\n"
        "comment_sender → linked-группа → Telegram\n"
        "    ↓\n"
        "comments (status: sent/failed) + logs"
    )
    pdf.body(
        "Каждый аккаунт проходит этот пайплайн независимо и параллельно, "
        "со своими настройками, prompt'ом и proxy."
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUTPUT))
    return OUTPUT


if __name__ == "__main__":
    path = build_pdf()
    print(f"PDF saved: {path}")
