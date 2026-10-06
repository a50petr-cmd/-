# Ежедневный поиск → Telegram (см. docs в Project Context: daily-search-10am.md)
$ErrorActionPreference = "Stop"
$repo = if ($env:JOB_AGENT_REPO) { $env:JOB_AGENT_REPO } else { "$env:USERPROFILE\job-agent" }
$store = if ($env:JOB_AGENT_STORE) { $env:JOB_AGENT_STORE } else { "$env:USERPROFILE\job-agent-store" }
$python = Join-Path $repo ".venv\Scripts\python.exe"
$log = Join-Path $store "search.log"

function Add-SearchLogLine([string]$Line) {
  Add-Content -Path $log -Value $Line -Encoding utf8
}

if (-not (Test-Path $python)) {
  Add-SearchLogLine "ERROR: venv not found at $python"
  exit 1
}

$env:JOB_AGENT_STORE = $store
$env:PYTHONPATH = $repo
if (-not $env:HH_USER_AGENT) {
  $env:HH_USER_AGENT = "PetroJobAgent/1.0 (alekseev.pa50@yandex.ru)"
}

$env:JOB_SCORE_NOTIFY_THRESHOLD = if ($env:JOB_SCORE_NOTIFY_THRESHOLD) { $env:JOB_SCORE_NOTIFY_THRESHOLD } else { "65" }

Set-Location $repo
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$dow = (Get-Date).DayOfWeek
if ($dow -eq "Saturday" -or $dow -eq "Sunday") {
  "=== $ts skip weekend (no search) ===" | Out-File -Append $log
  exit 0
}
"=== $ts daily search ===" | Out-File -Append $log

& $python -m job_agent search --hh-web-only --limit 40 --show 5 *>> $log
exit $LASTEXITCODE
