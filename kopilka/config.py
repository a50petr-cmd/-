import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    database_url: str


def load_settings() -> Settings:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    database_url = os.getenv("DATABASE_URL", "").strip()
    missing = []
    if not token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not database_url:
        missing.append("DATABASE_URL")
    if missing:
        names = ", ".join(missing)
        raise SystemExit(f"Не заданы переменные окружения: {names}. См. .env.example")
    return Settings(telegram_token=token, database_url=database_url)
