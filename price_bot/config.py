from __future__ import annotations

import os
from pathlib import Path

SECRETS_PATH = Path("/cursor/stores/self/internal/secrets.env")

# Polite delay between outbound marketplace requests (seconds).
REQUEST_MIN_INTERVAL = float(os.environ.get("PRICE_BOT_REQUEST_INTERVAL", "0.8"))

USER_AGENT = os.environ.get(
    "PRICE_BOT_USER_AGENT",
    "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
)

DEMO_MODE = os.environ.get("PRICE_BOT_DEMO", "").lower() in ("1", "true", "yes")


def load_dotenv_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def get_bot_token() -> str | None:
    token = os.environ.get("PRICE_BOT_TOKEN")
    if token:
        return token
    # Local fallback only: shared secrets file (do not commit).
    file_env = load_dotenv_file(SECRETS_PATH)
    return file_env.get("PRICE_BOT_TOKEN") or file_env.get("TELEGRAM_BOT_TOKEN")


def get_default_chat_id() -> str | None:
    chat = os.environ.get("PRICE_BOT_CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID")
    if chat:
        return chat
    file_env = load_dotenv_file(SECRETS_PATH)
    return file_env.get("TELEGRAM_CHAT_ID")
