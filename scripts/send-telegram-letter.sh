#!/usr/bin/env bash
# Отправить cover_letter из pending в Telegram (если CLI ещё без telegram-letter)
set -euo pipefail
ID="${1:?usage: send-telegram-letter.sh hh_web:12345}"
repo="${JOB_AGENT_REPO:-$HOME/job-agent}"
store="${JOB_AGENT_STORE:-$HOME/job-agent-store}"
cd "$repo"
source .venv/Scripts/activate
export JOB_AGENT_STORE="$store"
export PYTHONPATH="$repo"
python - <<PY
import os, sys
sys.path.insert(0, os.environ["PYTHONPATH"])
from job_agent.config import PROFILE_YAML
from job_agent.profile import load_profile
from job_agent.telegram_notifier import send_pending_cover_letter
uid = "$ID"
ok = send_pending_cover_letter(uid, load_profile(PROFILE_YAML))
print("Письмо отправлено в Telegram." if ok else "Не удалось отправить.")
raise SystemExit(0 if ok else 1)
PY
