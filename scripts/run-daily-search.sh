#!/usr/bin/env bash
# Ежедневный поиск → Telegram (для Git Bash / Планировщик с bash.exe)
set -euo pipefail
repo="${JOB_AGENT_REPO:-$HOME/job-agent}"
store="${JOB_AGENT_STORE:-$HOME/job-agent-store}"
cd "$repo"
# shellcheck source=/dev/null
source .venv/Scripts/activate
export JOB_AGENT_STORE="$store"
export PYTHONPATH="$repo"
export HH_USER_AGENT="${HH_USER_AGENT:-PetroJobAgent/1.0 (alekseev.pa50@yandex.ru)}"
export JOB_SCORE_NOTIFY_THRESHOLD="${JOB_SCORE_NOTIFY_THRESHOLD:-65}"
dow=$(date +%u)
if [ "$dow" -ge 6 ]; then
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') skip weekend (no search) ===" >> "$store/search.log"
  exit 0
fi
echo "=== $(date '+%Y-%m-%d %H:%M:%S') daily search ===" >> "$store/search.log"
python -m job_agent search --hh-web-only --limit 40 --show 5 >> "$store/search.log" 2>&1
