from __future__ import annotations

import os
from pathlib import Path

_CLOUD_STORE_ROOT = Path("/cursor/stores/self")
_DEFAULT_LOCAL_STORE = Path.home() / "job-agent-store"

# Polite delay between outbound marketplace requests (seconds).
REQUEST_MIN_INTERVAL = float(os.environ.get("PRICE_BOT_REQUEST_INTERVAL", "0.8"))

USER_AGENT = os.environ.get(
    "PRICE_BOT_USER_AGENT",
    "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
)

DEMO_MODE = os.environ.get("PRICE_BOT_DEMO", "").lower() in ("1", "true", "yes")


def get_store_root() -> Path:
    for key in ("PRICE_BOT_STORE", "JOB_AGENT_STORE"):
        raw = os.environ.get(key)
        if raw:
            return Path(raw).expanduser()
    cloud_secrets = _CLOUD_STORE_ROOT / "internal" / "secrets.env"
    if cloud_secrets.is_file():
        return _CLOUD_STORE_ROOT
    return _DEFAULT_LOCAL_STORE


def get_secrets_path() -> Path:
    return get_store_root() / "internal" / "secrets.env"


def _strip_env_value(value: str) -> str:
    return value.strip().strip('"').strip("'").rstrip("\r")


def load_dotenv_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().rstrip("\r")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip().rstrip("\r")] = _strip_env_value(value)
    return out


def get_bot_token() -> str | None:
    from price_bot.telegram_validate import normalize_bot_token

    raw = os.environ.get("PRICE_BOT_TOKEN")
    if raw is not None and raw.strip():
        return normalize_bot_token(raw)
    # Local fallback only: shared secrets file (do not commit).
    file_env = load_dotenv_file(get_secrets_path())
    if "PRICE_BOT_TOKEN" in file_env:
        price_token = file_env["PRICE_BOT_TOKEN"]
        if price_token:
            return normalize_bot_token(price_token)
        return None
    fallback = file_env.get("TELEGRAM_BOT_TOKEN")
    if fallback:
        return normalize_bot_token(fallback)
    return None


def get_default_chat_id() -> str | None:
    chat = os.environ.get("PRICE_BOT_CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID")
    if chat:
        return chat
    file_env = load_dotenv_file(get_secrets_path())
    return file_env.get("TELEGRAM_CHAT_ID")
