import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# Telegram API credentials — one pair for all accounts (from my.telegram.org)
API_ID: int = int(os.getenv("API_ID", "0") or "0")
API_HASH: str = os.getenv("API_HASH", "")

# Fallback GPT prompt (can be overridden per account in DB)
DEFAULT_GPT_PROMPT: str = os.getenv(
    "DEFAULT_GPT_PROMPT",
    "Пиши короткие шуточные безобидные комментарии, веди себя как настоящий человек. "
    "Длина комментария не более 7 слов.",
)

MAX_COMMENT_LENGTH: int = int(os.getenv("MAX_COMMENT_LENGTH", 500))

# Minimum post length to consider for commenting
MIN_POST_LENGTH: int = int(os.getenv("MIN_POST_LENGTH", 50))


def get_telegram_api() -> tuple[int, str]:
    """Returns global API_ID and API_HASH. Raises if not configured."""
    if not API_ID or not API_HASH:
        raise RuntimeError(
            "API_ID и API_HASH не заданы в .env\n"
            "Получи их на https://my.telegram.org и добавь в .env:\n"
            "  API_ID=12345678\n"
            "  API_HASH=abcdef..."
        )
    return API_ID, API_HASH
