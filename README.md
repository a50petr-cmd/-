# Бот вакансий операционного директора

Telegram-бот для Петра Алексеева. По рабочим дням в 09:00 по Москве он ищет новые вакансии COO и присылает сопроводительное письмо под каждую. Просмотренные вакансии, письма и привязка чата хранятся в Cloudflare KV, а не на компьютере.

Бот сам отклик не отправляет.

## Что ищет

Целевая роль: операционный директор (COO), директор по операционной деятельности, Head of Operations. Смежные роли вроде CEO попадают в подборку, только если в тексте вакансии прямо нужен операционный контур.

Город: Москва и Московская область, а также удалёнка и гибрид по России. Вакансии с обязательным переездом в другой город не присылаются.

Площадки:

- hh.ru
- Зарплата.ру
- Работа России (открытые данные)
- Хабр Карьера
- SuperJob, если задан ключ API

Авито и Работа.ру не подключены: у них нет устойчивого открытого API, а страницы поиска с серверов Cloudflare не отдают данные.

## Письмо

Текст собирается из фактов резюме от 23 сентября 2026: в письмо попадают 2–3 достижения, которые ближе к тексту вакансии. Новые цифры бот не придумывает.

Телефон и почта в репозиторий не входят, потому что он публичный. Добавьте их секретами Cloudflare, тогда они появятся в подписи. Telegram в подписи: https://t.me/PetroAlekseev

## Команды

- `/start` — привязать чат. Первый чат становится владельцем, если не задан `OWNER_CHAT_ID`.
- `/search` — прислать подборку сразу.
- `/pause` и `/resume` — ежедневная рассылка.
- `/status` — пауза, секреты и последний запуск.
- `/help`

Расписание: понедельник–пятница, 09:00 мск. Праздники 2026 и 2027 по производственному календарю пропускаются. В один день уходит не больше 5 новых вакансий.

## Запуск на Cloudflare

Нужен тариф Workers Paid: разбор страниц вакансий не укладывается в лимит CPU бесплатного плана.

```bash
npm install
npx wrangler login
npm run kv
```

Команда `npm run kv` печатает `id` namespace. Вставьте его в `wrangler.toml` вместо `replace-with-kv-namespace-id`.

Секреты:

```bash
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put WEBHOOK_SECRET
npx wrangler secret put CONTACT_PHONE
npx wrangler secret put CONTACT_EMAIL
```

Необязательно:

```bash
npx wrangler secret put OWNER_CHAT_ID
npx wrangler secret put SUPERJOB_API_KEY
```

`WEBHOOK_SECRET` — любая длинная случайная строка. `OWNER_CHAT_ID` можно взять из ответа на `/start`, если хотите зафиксировать чат.

Деплой и webhook:

```bash
npm run deploy
export TELEGRAM_BOT_TOKEN=...
export WEBHOOK_SECRET=...
export WORKER_URL=https://alekseev-job-bot.<account>.workers.dev
sh scripts/set-webhook.sh
```

В Telegram: `/start`, затем `/search`.

Токен бота создаётся в [@BotFather](https://t.me/BotFather). Ключ SuperJob — в кабинете разработчика SuperJob, заголовок `X-Api-App-Id`.

## Проверка локально

```bash
npm test
npm run typecheck
npm run search
```

`npm run search` ходит в живые площадки и печатает письма в терминал, в Telegram ничего не отправляет.
