# E-grocery basket MVP — сравнение корзины (Москва)

**Статус:** план (код не начат).  
**Аудитория:** Петр, опыт X5 / e-grocery.  
**Связь:** выбран [вариант A](./price-bot-next-directions.md) после [PetroPriceBot MVP](./price-bot-mvp.md).

---

## 1. Проблема и почему не Cheaper

**Задача пользователя:** не «где дешевле один SKU на маркетплейсе», а **итоговая стоимость типовой недельной корзины** при заказе **с доставкой на дом** в конкретном районе Москвы — с учётом того, что сервисы по-разному матчат товары, меняют цену по даркстору и навешивают условия на доставку.

**Cheaper / YoloPrice / Palert** хорошо закрывают:

- поиск **одной карточки** по артикулу/названию на Ozon, WB, Я.Маркет, mm.ru и десятках ритейлеров;
- промо, кэшбэк, иногда «итог с доставкой» для **маркетплейсных** сценариев (YoloPrice).

**Слабое место для e-grocery quick-commerce:**

| Фактор | Почему важно | Cheaper / агрегаторы |
|--------|--------------|----------------------|
| **Корзина (10–30 позиций)** | Экономия на молоке может съесть дорогие овощи | Обычно **поштучное** сравнение, не «собери корзину и сравни total» |
| **Доставка** | У Самоката часто «0 ₽», у других — порог бесплатной доставки | Редко **персональный** расчёт по адресу и слоту |
| **Мин. заказ** | Корзина 800 ₽ может быть недоступна в сервисе | Не всегда видно до checkout |
| **Замены / аналоги** | «Молоко 3,2% 900 мл» ≠ «950 мл другого бренда» | Нет единой модели **substitution** между Lavka и VkusVill |
| **Dark store / гео** | Цена и наличие зави от координат | Нужен явный **reference address** (Пetro — Москва, район уточнить) |
| **Fresh-витрины** | Ozon Fresh, Lavka, Самокат — не те же API, что Ozon Seller | В Cheaper нет фокуса на **express grocery** |

**Конкуренты в нише (ориентир, не копировать):**

- [DostavkaObzor — калькулятор корзины](https://www.dostavkaobzor.ru/calculator) — фиксированный набор продуктов, периодический сбор, **оценочная** доставка.
- [FoodsPrice](https://foodsprice.ru/) — корзина для **офлайн/гипер** сетей (Пятёрочка, Лента, …), не quick-commerce 15–30 мин.

**Наша ниша:** Telegram-first **оценка корзины** по 4–6 express-сервисам Москвы, с **честной** пометкой «estimate / не checkout», ссылками на найденные SKU и явным P0-маппингом «канонический товар → SKU в магазине».

---

## 2. Целевые сервисы (Москва) — web/API feasibility

Краткий обзор (2026-10-06, открытые источники + опыт price_bot). **Официального consumer API** почти нигде нет; feasibility = «можно ли стабильно получать search + price + URL для адреса».

| Сервис | Витрина | Consumer API | Практический путь MVP | Приоритет MVP |
|--------|---------|--------------|------------------------|---------------|
| **Яндекс Лавка** | [lavka.yandex.ru](https://lavka.yandex.ru) | Нет публичного | Web/mobile internal API по **lat/lon** (категории, карточки); community scrapers (Apify и др.) | **P0** — хороший search по категориям |
| **Самокат** | [web.samokat.ru](https://web.samokat.ru) | Нет (Postman — только orders под auth) | **Адрес обязателен**; Selenium/Playwright или перехват app API; парсеры на GitHub | **P0** — эталон QC, но самый капризный |
| **Ozon Fresh** | Раздел на [ozon.ru](https://www.ozon.ru) | Нет (Seller API — не Fresh) | Тот же риск **403**, что в price_bot; отдельная витрина Fresh по городу; composer/HTML fallback | **P0** — переиспользовать ozon-адаптер price_bot |
| **ВкусВилл доставка** | [vkusvill.ru](https://vkusvill.ru/goods/) | **Да:** [MCP API](https://mcp.vkusvill.ru/) (`vkusvill_products_search`, cart link) | Лучший старт для P1 search; **наличие по адресу** — только через сайт (Puppeteer / cookies), см. community `vv-checker` | **P0** — единственный «официальный» search |
| **Перекрёсток / Vprok** | [perekrestok.ru](https://www.perekrestok.ru), [vprok.ru](https://vprok.ru) | Нет официального | Неофициальный `perekrestok_api` (эмуляция web); Vprok — отдельная витрина X5, отдельный адаптер | **P1** — после Lavka/VV |
| **Магнит Доставка** | [magnit.ru](https://magnit.ru), [dostavka.magnit.ru](https://dostavka.magnit.ru) | B2B/Partner — не consumer | Известны **mobile** endpoints (`POST /v2/goods/search`, `storeCode`); web XHR при выборе `shopCode` | **P1** — полезен для «гипер vs express» |

**Рекомендуемый состав MVP (2 недели):** Lavka + VkusVill + Ozon Fresh + Самокат (4 колонки). Perekrestok/Vprok и Magnit — заглушки «скоро» или P1, если P0 стабилен.

**Reference geo (зафиксировать с Петром):** одна точка в Москве (например, центр или домашний адрес), lat/lon + текст для бота. Все цены — **для этой точки**, в ответе всегда disclaimer.

---

## 3. Scope MVP

### Пользовательский сценарий

1. Пользователь пишет боту **список продуктов** (свободный текст, по одному на строку) **или** команду `/basket` с **фиксированной корзиной** из YAML.
2. Бот отвечает таблицей (Markdown/HTML в Telegram):

   - строки = канонические позиции корзины;
   - колонки = сервисы;
   - ячейка = найденный SKU, цена × qty, **ссылка**, пометка match (`exact` / `fuzzy` / `missing`);
   - footer = **subtotal**, **оценка доставки** (если известна), **итого**, **мин. заказ** (если известен).

3. В каждом ответе — блок **«Честно про точность»**: витринные цены, без карты лояльности, замены не подтверждены, доставка может отличаться.

### Фиксированная корзина (YAML)

Хранить в репозитории / store, например `docs/baskets/moscow-weekly-starter.yaml`:

```yaml
id: moscow-weekly-starter
region: moscow
items:
  - id: milk-32-900
    name: "Молоко 3,2% ~900 мл"
    qty: 2
    unit: pcs
  - id: eggs-10
    name: "Яйца С0/C1, 10 шт"
    qty: 1
```

P0: маппинг `item.id → { lavka: slug/url, vkusvill: xml_id, ... }` в `data/sku-map.yaml` (ручной).

### Архитектура (выбор)

**Рекомендация:** новый пакет **`grocery_bot`** (или `basket_bot`) в том же репо, что `price_bot` и job-agent — **переиспользовать** Telegram loop, secrets, форматирование сообщений, интервалы HTTP.

**Альтернатива:** расширить `price_bot` — хуже по смыслу (другой domain, другие адаптеры); не делать без явной просьбы.

**Не в MVP:** OAuth в личные кабинеты, автоматический checkout, push-алерты, история цен 90 дней, iOS/Android.

---

## 4. Фазы

### P0 — Manual SKU mapping (неделя 1)

- Зафиксировать **reference address** (Москва).
- Корзина 15–20 «базовых» SKU (молоко, яйца, хлеб, курица, рис, …).
- Таблица `sku-map.yaml`: для каждого `item.id` — прямые URL / id по магазинам (ручной сбор 1–2 часа на магазин).
- Адаптер «fetch price by known URL/id» (минимум HTTP; Playwright только где без вариантов).
- Telegram: `/basket moscow-weekly-starter` → таблица + totals.

**Критерий готовности:** 4 сервиса × 15 позиций, ≥80% позиций с ценой, остальные явно `missing`.

### P1 — Semi-auto search per store (неделя 2 +)

- Для каждого канонического `name` → search API/scrape магазина → top-3 кандидата → эвристика (название, вес, бренд) + **confidence**.
- VkusVill: `vkusvill_products_search`.
- Lavka / Ozon Fresh / Samokat: search endpoint или Playwright search box.
- Human-in-the-loop: при confidence &lt; порога — показывать «выберите вариант» (inline кнопки Telegram) — опционально после MVP.

### P2 — Address + delivery slot

- Сохранённый адрес пользователя (один на чат) в store (`internal/grocery-profiles/`).
- Расчёт **delivery fee**, **min basket**, **nearest slot** (где API/checkout preview доступен).
- Samokat / Lavka: сессия + geo; Magnit: `storeCode` от адреса.
- Предупреждение о **substitutions** при сборке (только текстовое, без симуляции).

---

## 5. Технические риски

| Риск | Аналог | Митигация |
|------|--------|-----------|
| **403 / anti-bot** (Ozon, WB-опыт) | [price-bot-mvp.md](./price-bot-mvp.md) — Ozon composer 403 | Desktop UA, HTML fallback; **запуск с домашнего IP** Петра; не облако для production fetch |
| **Нет stable API** (Samokat, Lavka) | — | Playwright headless, rate limit, кэш Redis/файл 15–60 мин |
| **ToS / legal** | Парсинг витрины | Только личное использование MVP; не продавать данные; robots.txt respect где возможно |
| **SKU drift** | Товары меняют id | Версионирование `sku-map`, дата последней проверки в ответе |
| **Сопоставление «то же молоко»** | Fuzzy title match | P0 — ручной map; P1 — вес/бренд regex + порог |
| **Telegram timeout** | price_bot фон + «Ищу…» | Тот же паттерн: async job, chunking таблицы |
| **Секреты** | `PRICE_BOT_TOKEN` vs job bot | Отдельный `GROCERY_BOT_TOKEN` или переименование общего price-бота — решить с Петром |

**Playwright vs requests:** P0 — максимум **requests** + VkusVill MCP; Playwright подключать для Samokat/Lavka search в P1. Official APIs: только VkusVill MCP в MVP; Magnit mobile API — P1 с осторожностью (не документирован для third parties).

---

## 6. Чеклист MVP (~2 недели)

### Неделя 1

- [ ] Согласовать reference address (Москва) и состав корзины 15–20 SKU.
- [ ] Repo: пакет `grocery_bot`, entrypoint `python -m grocery_bot`.
- [ ] Переиспользовать: загрузка `JOB_AGENT_STORE`, `internal/secrets.env`, Telegram polling из price_bot.
- [ ] `docs/baskets/moscow-weekly-starter.yaml` + `data/sku-map.yaml` (ручное наполнение).
- [ ] Адаптеры **fetch by id/url**: VkusVill (MCP или HTTP), Ozon Fresh (reuse ozon helpers), Lavka, Samokat — хотя бы 2 из 4.
- [ ] Aggregator: line totals, grand total, форматирование Markdown для Telegram.
- [ ] CLI: `python -m grocery_bot basket --yaml moscow-weekly-starter` (без Telegram).
- [ ] Disclaimer в каждом ответе (estimate).

### Неделя 2

- [ ] Довести до 4 сервисов на P0-маппинге.
- [ ] Telegram: свободный список продуктов → временно маппинг только по YAML aliases (или «не поддержано»).
- [ ] P1 spike: search на VkusVill + один scraper-сервис.
- [ ] Кэш цен (file/sqlite) + `fetched_at` в выводе.
- [ ] Док: запуск на Windows ([windows-install.md](./windows-install.md)), env vars.
- [ ] Демо-запись / скрин для Петра: одна корзина, 4 колонки.

**Out of scope для 2 недель:** личный кабинет, оплата, P2 delivery slots, Perekrestok/Magnit production.

---

## 7. Переиспользование из price_bot / job-agent

| Компонент | Где | Как использовать |
|-----------|-----|------------------|
| **Telegram** | `price_bot` — long polling, retry send, фоновые задачи | Скопировать/вынести общий `telegram_util` или импорт паттернов |
| **Secrets** | `JOB_AGENT_STORE/internal/secrets.env` | `GROCERY_BOT_TOKEN` или `PRICE_BOT_TOKEN`; тот же путь через [price-bot-mvp.md](./price-bot-mvp.md) |
| **JOB_AGENT_STORE** | `~/job-agent-store` на Windows | Конфиг корзины, sku-map, кэш — под `docs/` или `internal/grocery/` в store |
| **HTTP discipline** | `PRICE_BOT_REQUEST_INTERVAL`, UA, Referer | Те же env для grocery adapters |
| **Ozon** | composer + HTML fallback | Ветка Fresh: другой URL, те же 403-уроки |
| **CLI + `--demo`** | price_bot compare --demo | `--demo` с фикстурами для CI и UI-теста без сети |
| **Документация** | job-agent setup, Git Bash | Единый стиль с [job-agent-setup.md](./job-agent-setup.md) |

**Repo:** ожидается тот же monorepo, что job-agent / price_bot ([PR #2](https://github.com/a50petr-cmd/-/pull/2)); новая ветка `cursor/grocery-basket-mvp-5ab5` при старте кода.

---

## Открытые решения (для Петра)

1. Reference address (район Москвы).
2. Отдельный Telegram-бот или переиспользовать price-бот с командами `/basket`?
3. Первые 4 сервиса: согласны Lavka + VV + Ozon Fresh + Samokat?
4. Язык UI бота: только RU?

---

## Ссылки

- [price-bot-next-directions.md](./price-bot-next-directions.md) — выбор направления A  
- [price-bot-mvp.md](./price-bot-mvp.md) — Telegram, secrets, 403  
- [marketplace-price-comparison-research.md](./marketplace-price-comparison-research.md) — Cheaper и щели  
- [VkusVill MCP](https://mcp.vkusvill.ru/)  
- [DostavkaObzor calculator](https://www.dostavkaobzor.ru/calculator) — бенчмарк UX корзины  

---

## Petro config (P0)

Канонические YAML лежат в **Context / JOB_AGENT_STORE** (на Windows обычно `%USERPROFILE%\job-agent-store`):

| Файл | Назначение |
|------|------------|
| `docs/e-grocery-location.yaml` | Точка доставки: **Электросталь**, МО; сервисы `samokat`, `yandex_lavka`, `vkusvill`; `ozon_fresh` отложен |
| `docs/e-grocery-basket-starter.yaml` | Стартовая корзина (7 позиций: молоко, яйца, морковь, тушёнка, батон, грудка, томатная паста) |

Пакет `egrocery` читает эти пути по умолчанию, когда задан `JOB_AGENT_STORE` (или `EGROCERY_STORE`):

```text
$JOB_AGENT_STORE/docs/e-grocery-location.yaml
$JOB_AGENT_STORE/docs/e-grocery-basket-starter.yaml
```

Переопределение: `EGROCERY_LOCATION_YAML`, `EGROCERY_BASKET_YAML`.

**Покрытие доставки:** перед живыми ценами нужно проверить, что **Самокат** и **Яндекс Лавка** доставляют на ваш адрес в Электростали (координаты/улица — в `address_note` location YAML). P0 выводит таблицу с placeholder `—` в ячейках цен.

**VkusVill:** для автопоиска позже — env `VKUSVILL_MCP_URL` ([MCP API](https://mcp.vkusvill.ru/)); в P0 клиент не реализован, только заглушка.

**CLI:**

```powershell
$env:JOB_AGENT_STORE = "$HOME\job-agent-store"
python -m egrocery basket
```

