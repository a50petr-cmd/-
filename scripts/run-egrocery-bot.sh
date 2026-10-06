#!/usr/bin/env bash
# Git Bash on Windows: activate venv and run the Telegram bot.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export JOB_AGENT_STORE="${JOB_AGENT_STORE:-$HOME/job-agent-store}"
export PYTHONUNBUFFERED=1

echo "egrocery: JOB_AGENT_STORE=$JOB_AGENT_STORE"
if [[ ! -f "$JOB_AGENT_STORE/internal/secrets.env" ]]; then
  echo "egrocery: WARNING — no secrets.env at $JOB_AGENT_STORE/internal/secrets.env" >&2
fi
echo "egrocery: activating .venv …"
# shellcheck source=/dev/null
source .venv/Scripts/activate
echo "egrocery: launch (Ctrl+C to stop; up to ~30s quiet between log lines is OK)"
exec python -u -m egrocery bot
