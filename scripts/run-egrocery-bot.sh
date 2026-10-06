#!/usr/bin/env bash
# Git Bash on Windows: activate venv and run the Telegram bot.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=/dev/null
source .venv/Scripts/activate
export JOB_AGENT_STORE="${JOB_AGENT_STORE:-$HOME/job-agent-store}"
exec python -m egrocery bot
