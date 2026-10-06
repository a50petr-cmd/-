# Alekseev — Job Agent

CLI `job_agent/` для поиска вакансий на рунете (HeadHunter, Habr Career, опционально Superjob), скoring и подготовки откликов с human-in-the-loop.

Документация пользователя: см. Agent Store `docs/job-agent-setup.md` и `docs/job-search-profile.md`.

## Быстрый старт

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export HH_USER_AGENT='PetroJobAgent/1.0 (your@email.com)'
python -m job_agent search --use-fixtures   # если HH API недоступен с вашего IP
python -m job_agent pending
python -m job_agent approve 'hh:123456789'
```
