from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


DEFAULT_STORE_ROOT = Path(os.environ.get("JOB_AGENT_STORE", "/cursor/stores/self"))
_load_dotenv_file(DEFAULT_STORE_ROOT / "internal" / "secrets.env")
PROFILE_YAML = DEFAULT_STORE_ROOT / "docs" / "profile.yaml"
PROFILE_MD = DEFAULT_STORE_ROOT / "docs" / "job-search-profile.md"
PENDING_DIR = DEFAULT_STORE_ROOT / "internal" / "pending-applications"

HH_USER_AGENT = os.environ.get(
    "HH_USER_AGENT",
    "PetroJobAgent/1.0 (petro.job.search@users.noreply.github.com)",
)
HH_API_BASE = "https://api.hh.ru"
HH_WEB_BASE = "https://hh.ru"
HH_RATE_DELAY_SEC = float(os.environ.get("HH_RATE_DELAY_SEC", "0.34"))
HH_WEB_USER_AGENT = os.environ.get(
    "HH_WEB_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
)

HABR_BASE = "https://career.habr.com"
HABR_RATE_DELAY_SEC = float(os.environ.get("HABR_RATE_DELAY_SEC", "1.0"))

SUPERJOB_API_BASE = "https://api.superjob.ru/2.0"
SUPERJOB_APP_ID = os.environ.get("SUPERJOB_APP_ID", "")

SCORE_NOTIFY_THRESHOLD = int(os.environ.get("JOB_SCORE_NOTIFY_THRESHOLD", "70"))
AUTO_APPLY = os.environ.get("JOB_AGENT_AUTO_APPLY", "").lower() in ("1", "true", "yes")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_INCLUDE_COVER_LETTERS = os.environ.get(
    "TELEGRAM_INCLUDE_COVER_LETTERS", "1"
).lower() in ("1", "true", "yes")

RESUME_PDF = os.environ.get(
    "RESUME_PDF",
    "/home/ubuntu/.cursor/projects/workspace/uploads/____________________________71ec.pdf",
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
