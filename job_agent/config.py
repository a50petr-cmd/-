from __future__ import annotations

import os
from pathlib import Path

DEFAULT_STORE_ROOT = Path(os.environ.get("JOB_AGENT_STORE", "/cursor/stores/self"))
PROFILE_YAML = DEFAULT_STORE_ROOT / "docs" / "profile.yaml"
PROFILE_MD = DEFAULT_STORE_ROOT / "docs" / "job-search-profile.md"
PENDING_DIR = DEFAULT_STORE_ROOT / "internal" / "pending-applications"

HH_USER_AGENT = os.environ.get(
    "HH_USER_AGENT",
    "PetroJobAgent/1.0 (petro.job.search@users.noreply.github.com)",
)
HH_API_BASE = "https://api.hh.ru"
HH_RATE_DELAY_SEC = float(os.environ.get("HH_RATE_DELAY_SEC", "0.34"))

HABR_BASE = "https://career.habr.com"
HABR_RATE_DELAY_SEC = float(os.environ.get("HABR_RATE_DELAY_SEC", "1.0"))

SUPERJOB_API_BASE = "https://api.superjob.ru/2.0"
SUPERJOB_APP_ID = os.environ.get("SUPERJOB_APP_ID", "")

SCORE_NOTIFY_THRESHOLD = int(os.environ.get("JOB_SCORE_NOTIFY_THRESHOLD", "70"))
AUTO_APPLY = os.environ.get("JOB_AGENT_AUTO_APPLY", "").lower() in ("1", "true", "yes")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

RESUME_PDF = os.environ.get(
    "RESUME_PDF",
    "/home/ubuntu/.cursor/projects/workspace/uploads/____________________________71ec.pdf",
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
