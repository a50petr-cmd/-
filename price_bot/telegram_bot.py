from __future__ import annotations

import logging
import time
from typing import Any

import requests

from price_bot.compare import compare_url
from price_bot.config import get_bot_token
from price_bot.formatters import format_comparison_message
from price_bot.url_parser import parse_product_url

log = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}/{method}"


class TelegramBot:
    def __init__(self, token: str) -> None:
        self.token = token
        self.offset: int | None = None

    def _call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = API_BASE.format(token=self.token, method=method)
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data}")
        return data

    def send_message(self, chat_id: int | str, text: str) -> None:
        # Telegram limit 4096 chars
        chunk_size = 4000
        for i in range(0, len(text), chunk_size):
            self._call(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": text[i : i + chunk_size],
                    "disable_web_page_preview": True,
                },
            )

    def get_updates(self, timeout: int = 30) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"timeout": timeout}
        if self.offset is not None:
            payload["offset"] = self.offset
        data = self._call("getUpdates", payload)
        return data.get("result", [])

    def handle_text(self, chat_id: int | str, text: str) -> None:
        stripped = text.strip()
        if stripped.startswith("/start"):
            self.send_message(
                chat_id,
                "Пришлите ссылку на товар с Ozon, Wildberries или Яндекс Маркета — "
                "найду похожие предложения и сравню цены.",
            )
            return
        if stripped.startswith("/help"):
            self.send_message(
                chat_id,
                "Команды:\n/start — приветствие\n/help — помощь\n\n"
                "Отправьте URL карточки товара на одном из маркетплейсов.",
            )
            return

        if "http" not in stripped and not any(
            d in stripped.lower()
            for d in ("ozon.ru", "wildberries.ru", "market.yandex.ru")
        ):
            self.send_message(chat_id, "Нужна ссылка на товар (Ozon / WB / Яндекс Маркет).")
            return

        try:
            parse_product_url(stripped)
        except ValueError as exc:
            self.send_message(chat_id, str(exc))
            return

        self.send_message(chat_id, "Ищу цены на трёх площадках, подождите…")
        try:
            result = compare_url(stripped)
            self.send_message(chat_id, format_comparison_message(result))
        except ValueError as exc:
            self.send_message(chat_id, f"Не удалось сравнить: {exc}")
        except Exception as exc:  # noqa: BLE001
            log.exception("compare failed")
            self.send_message(chat_id, f"Ошибка: {exc}")

    def process_update(self, update: dict[str, Any]) -> None:
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return
        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        text = msg.get("text")
        if chat_id is None or not text:
            return
        self.handle_text(chat_id, text)

    def run_polling(self) -> None:
        log.info("Starting Telegram long polling")
        while True:
            try:
                updates = self.get_updates(timeout=30)
                for upd in updates:
                    self.offset = upd["update_id"] + 1
                    self.process_update(upd)
            except KeyboardInterrupt:
                log.info("Stopped by user")
                break
            except Exception as exc:  # noqa: BLE001
                log.warning("Polling error: %s", exc)
                time.sleep(3)


def run_bot() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    token = get_bot_token()
    if not token:
        raise SystemExit(
            "Set PRICE_BOT_TOKEN (recommended) or TELEGRAM_BOT_TOKEN in env, "
            "or in {store}/internal/secrets.env "
            "(set JOB_AGENT_STORE or PRICE_BOT_STORE to your store root)."
        )
    TelegramBot(token).run_polling()
