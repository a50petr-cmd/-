# Отклик на HeadHunter (Playwright, локально)

## Принципы

- **Пароль HH не сохраняется** в проекте и не передаётся агенту.
- Сессия браузера хранится только в `~/.hh-playwright-profile` на вашем компьютере.
- По умолчанию пайплайн **не отправляет** отклики — только после `python -m job_agent approve <id>`.

## Установка

```bash
pip install -r requirements.txt
playwright install chromium
```

## Шаги

1. Одобрите вакансию: `python -m job_agent approve hh:123456789`
2. Откройте JSON в `internal/pending-applications/`
3. Запустите:

```bash
python job_agent/apply/playwright_apply.py \
  --pending-json /path/to/internal/pending-applications/hh_123456789.json \
  --headed
```

4. При первом запуске войдите на hh.ru в открывшемся окне.
5. Скрипт откроет страницу вакансии и выведет сопроводительное письмо — вставьте в форму и нажмите «Откликнуться».

## Habr Career

Обычно отклик через сайт с резюме на Хабре; автоматизацию не включаем — используйте ссылку из pending JSON.
