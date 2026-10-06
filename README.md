# Alekseev utilities

## price_bot (MVP)

Telegram bot and CLI to compare prices for the same or similar product across **Ozon**, **Wildberries**, and **Yandex Market**.

```bash
pip install -r requirements.txt
export PRICE_BOT_TOKEN=...   # from @BotFather
python -m price_bot compare "https://www.wildberries.ru/catalog/177900896/detail.aspx" --demo
python -m price_bot bot        # long polling
```

See project docs: `price-bot-mvp.md` in Cursor Project store (`docs/`).
