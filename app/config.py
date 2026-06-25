import os
import json
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

# --- Общие настройки ---
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")

DELAY_MIN: int = int(os.getenv("DELAY_MIN", 150))
DELAY_MAX: int = int(os.getenv("DELAY_MAX", 600))
JOIN_DELAY_MIN: int = int(os.getenv("JOIN_DELAY_MIN", 60))
JOIN_DELAY_MAX: int = int(os.getenv("JOIN_DELAY_MAX", 180))
MAX_COMMENT_LENGTH: int = int(os.getenv("MAX_COMMENT_LENGTH", 200))
SYSTEM_PROMPT: str = os.getenv(
    "SYSTEM_PROMPT",
    "Пиши короткие шуточные безобидные комментарии, веди себя как настоящий человек. "
    "Длина комментария не более 7 слов.",
)


@dataclass
class AccountConfig:
    """Конфигурация одного Telegram-аккаунта."""
    name: str
    api_id: int
    api_hash: str
    # phone используется только при первой авторизации (интерактивно)
    phone: str = ""
    # Если задан — используется вместо глобального MY_CHANNELS
    channels: List[str] = field(default_factory=list)

    @property
    def session_path(self) -> str:
        return f"data/sessions/{self.name}"


def load_accounts(path: str = "accounts.json") -> List[AccountConfig]:
    """
    Загружает список аккаунтов из JSON-файла.
    Формат файла описан в accounts.json.example.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Файл аккаунтов '{path}' не найден. "
            "Скопируйте accounts.json.example → accounts.json и заполните данные."
        )
    with open(path, encoding="utf-8") as f:
        raw: list = json.load(f)

    accounts = []
    for item in raw:
        accounts.append(
            AccountConfig(
                name=item["name"],
                api_id=int(item["api_id"]),
                api_hash=item["api_hash"],
                phone=item.get("phone", ""),
                channels=item.get("channels", []),
            )
        )
    if not accounts:
        raise ValueError("accounts.json пуст — добавьте хотя бы один аккаунт.")
    return accounts
