from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from egrocery.basket_service import build_basket_markdown
from egrocery.config import get_bot_token, get_store_root
from egrocery.delivery_point import save_user_delivery_point
from egrocery.geocode import geocode_address_yandex, get_yandex_geocoder_api_key

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
MAX_MESSAGE_LEN = 4000


class TelegramBot:
    def __init__(self, token: str) -> None:
        self.token = token
        self.pending_address: set[int] = set()
        self.offset: int | None = None

    def _api(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = TELEGRAM_API.format(token=self.token, method=method)
        data = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        if not body.get("ok"):
            raise RuntimeError(f"Telegram API {method} failed: {body}")
        return body["result"]

    def send_message(self, chat_id: int, text: str) -> None:
        if len(text) <= MAX_MESSAGE_LEN:
            self._api("sendMessage", {"chat_id": chat_id, "text": text})
            return
        chunk = ""
        for line in text.splitlines(keepends=True):
            if len(chunk) + len(line) > MAX_MESSAGE_LEN:
                self._api("sendMessage", {"chat_id": chat_id, "text": chunk})
                chunk = ""
            chunk += line
        if chunk:
            self._api("sendMessage", {"chat_id": chat_id, "text": chunk})

    def handle_start(self, chat_id: int) -> None:
        self.send_message(
            chat_id,
            "Привет! Я сравниваю корзину для доставки (Samokat, Lavka, VkusVill).\n\n"
            "1) /address — задайте адрес текстом или отправьте геопозицию 📍\n"
            "2) /basket — таблица цен для сохранённой точки доставки",
        )

    def handle_address_prompt(self, chat_id: int) -> None:
        self.pending_address.add(chat_id)
        self.send_message(
            chat_id,
            "Отправьте адрес текстом (например, «Электросталь, ул. …, д. …») "
            "или нажмите «Поделиться геолокацией» в Telegram.",
        )

    def save_location_pin(self, chat_id: int, lat: float, lon: float) -> None:
        store = get_store_root()
        point = save_user_delivery_point(store, chat_id, lat=lat, lon=lon)
        self.pending_address.discard(chat_id)
        self.send_message(
            chat_id,
            f"Сохранена геопозиция: {point.geo_summary()}\n"
            "Теперь можно вызвать /basket.",
        )

    def save_address_text(self, chat_id: int, address: str) -> None:
        store = get_store_root()
        warning: str | None = None
        lat: float | None = None
        lon: float | None = None
        city: str | None = None
        if get_yandex_geocoder_api_key():
            try:
                result = geocode_address_yandex(address)
            except urllib.error.URLError as exc:
                logger.warning("geocode failed: %s", exc)
                result = None
                warning = (
                    "Геокодер недоступен — сохранён только текст адреса. "
                    "Можно отправить геопозицию."
                )
            else:
                if result:
                    lat, lon = result.lat, result.lon
                    city = result.city
                else:
                    warning = (
                        "Адрес не распознан геокодером — сохранён текст. "
                        "Пришлите геопозицию для точных цен."
                    )
        else:
            warning = (
                "YANDEX_GEOCODER_API_KEY не задан — сохранён текст адреса без координат. "
                "Можно отправить геопозицию или добавить ключ в secrets.env."
            )
        point = save_user_delivery_point(
            store,
            chat_id,
            address_text=address.strip(),
            lat=lat,
            lon=lon,
            city=city,
            geocode_warning=warning,
        )
        self.pending_address.discard(chat_id)
        lines = [f"Адрес сохранён: {point.geo_summary()}"]
        if warning:
            lines.append(warning)
        lines.append("Вызовите /basket для сравнения.")
        self.send_message(chat_id, "\n".join(lines))

    def handle_basket(self, chat_id: int) -> None:
        text = build_basket_markdown(chat_id=chat_id)
        self.send_message(chat_id, text)

    def handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return
        chat_id = int(chat_id)

        if message.get("location"):
            loc = message["location"]
            self.save_location_pin(chat_id, float(loc["latitude"]), float(loc["longitude"]))
            return

        text = (message.get("text") or "").strip()
        if not text:
            return

        if text.startswith("/start"):
            self.handle_start(chat_id)
            return
        if text.startswith("/address"):
            self.handle_address_prompt(chat_id)
            return
        if text.startswith("/basket"):
            self.handle_basket(chat_id)
            return

        if chat_id in self.pending_address and not text.startswith("/"):
            self.save_address_text(chat_id, text)

    def run_polling(self, *, timeout: int = 30) -> None:
        logger.info("egrocery bot polling started")
        while True:
            params: dict[str, Any] = {"timeout": timeout}
            if self.offset is not None:
                params["offset"] = self.offset
            url = TELEGRAM_API.format(token=self.token, method="getUpdates")
            req = urllib.request.Request(
                url,
                data=json.dumps(params).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout + 10) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
            except urllib.error.URLError as exc:
                logger.warning("getUpdates error: %s", exc)
                time.sleep(3)
                continue
            if not body.get("ok"):
                logger.warning("getUpdates not ok: %s", body)
                time.sleep(3)
                continue
            for update in body.get("result", []):
                self.offset = int(update["update_id"]) + 1
                try:
                    self.handle_update(update)
                except Exception:
                    logger.exception("failed to handle update %s", update.get("update_id"))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    token = get_bot_token()
    if not token:
        raise SystemExit(
            "EGROCERY_BOT_TOKEN is not set (env or JOB_AGENT_STORE/internal/secrets.env)."
        )
    TelegramBot(token).run_polling()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
