import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# Fallback GPT prompt (can be overridden per account in DB)
DEFAULT_GPT_PROMPT: str = os.getenv(
    "DEFAULT_GPT_PROMPT",
    "Пиши короткие шуточные безобидные комментарии, веди себя как настоящий человек. "
    "Длина комментария не более 7 слов.",
)

MAX_COMMENT_LENGTH: int = int(os.getenv("MAX_COMMENT_LENGTH", 200))

# Minimum post length to consider for commenting
MIN_POST_LENGTH: int = int(os.getenv("MIN_POST_LENGTH", 50))
