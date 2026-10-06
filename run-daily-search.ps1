# Ежедневный поиск → Telegram (см. Project Context: daily-search-10am.md)
$ErrorActionPreference = "Stop"
$repo = if ($env:JOB_AGENT_REPO) { $env:JOB_AGENT_REPO } else { "$env:USERPROFILE\job-agent" }
$store = if ($env:JOB_AGENT_STORE) { $env:JOB_AGENT_STORE } else { "$env:USERPROFILE\job-agent-store" }
$python = Join-Path $repo ".venv\Scripts\python.exe"
$log = Join-Path $store "search.log"

if (-not (Test-Path $python)) {
  "ERROR: venv not found at $python" | Out-File -Append $log
  exit 1
}

$env:JOB_AGENT_STORE = $store
$env:PYTHONPATH = $repo
if (-not $env:HH_USER_AGENT) {
  $env:HH_USER_AGENT = "PetroJobAgent/1.0 (alekseev.pa50@yandex.ru)"
}

Set-Location $repo
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"=== $ts daily search ===" | Out-File -Append $log

& $python -m job_agent search --hh-web-only --limit 40 --show 5 2>&1 | Out-File -Append $log
exit $LASTEXITCODE
