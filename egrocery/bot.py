from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from egrocery.basket_service import build_basket_markdown
from egrocery.search_service import build_search_markdown
from egrocery.config import get_bot_token, get_store_root
from egrocery.delivery_point import save_user_delivery_point
from egrocery.geocode import geocode_address_with_warning
from egrocery.loaders import load_location
from egrocery.models import Location
from egrocery.telegram_util import parse_bot_command

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
MAX_MESSAGE_LEN = 4000
BOT_BUILD = "2026-03-24-deadlock-fix"


def _handler_max_sec() -> float:
    raw = os.environ.get("EGROCERY_HANDLER_MAX_SEC", "55").strip()
    try:
        return max(10.0, float(raw))
    except ValueError:
        return 55.0


class TelegramBot:
    def __init__(self, token: str) -> None:
        self.token = token
        self.pending_address: set[int] = set()
        self.offset: int | None = None

    def _api(
        self,
        method: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: float | tuple[float, float] = 20.0,
    ) -> dict[str, Any]:
        url = TELEGRAM_API.format(token=self.token, method=method)
        data = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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

    def send_typing(self, chat_id: int) -> None:
        try:
            self._api("sendChatAction", {"chat_id": chat_id, "action": "typing"})
        except Exception:
            logger.debug("sendChatAction failed", exc_info=True)

    def _reply_error(self, chat_id: int, exc: BaseException) -> None:
        logger.exception("handler error chat_id=%s", chat_id)
        try:
            self.send_message(
                chat_id,
                "Не удалось обработать запрос. Попробуйте ещё раз через минуту "
                f"или отправьте 📍 геопозицию.\n\n_({type(exc).__name__})_",
            )
        except Exception:
            logger.exception("failed to send error to chat_id=%s", chat_id)

    def handle_ping(self, chat_id: int) -> None:
        self.send_message(chat_id, f"pong ({BOT_BUILD}) — бот на связи.")

    def handle_start(self, chat_id: int) -> None:
        self.send_message(
            chat_id,
            f"Привет! ({BOT_BUILD})\n"
            "Я сравниваю корзину для доставки (Samokat, Lavka, VkusVill).\n\n"
            "1) /address — задайте адрес текстом или отправьте геопозицию 📍\n"
            "   Можно сразу: /address Электросталь, ул. …, д. …\n"
            "2) /basket — таблица цен для сохранённой точки доставки\n"
            "3) /search молоко 1.5% или /item … — самый дешёвый вариант по сервисам",
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
            "Теперь можно /search или /basket.",
        )

    def save_address_text(self, chat_id: int, address: str) -> None:
        self.send_typing(chat_id)
        self.send_message(chat_id, "Сохраняю адрес и ищу координаты…")
        store = get_store_root()
        location_path = store / "docs" / "e-grocery-location.yaml"
        if location_path.is_file():
            location = load_location(location_path)
        else:
            location = Location(
                city="Электросталь",
                region="Московская область",
                country="RU",
                services_enabled=("samokat", "yandex_lavka", "vkusvill"),
                services_deferred=("ozon_fresh",),
            )
        result, warning = geocode_address_with_warning(
            address.strip(),
            city=location.city,
            region=location.region,
            country=location.country,
        )
        lat: float | None = result.lat if result else None
        lon: float | None = result.lon if result else None
        city: str | None = result.city if result else None
        geocode_warning: str | None = warning if warning else ("" if result else None)
        point = save_user_delivery_point(
            store,
            chat_id,
            address_text=address.strip(),
            lat=lat,
            lon=lon,
            city=city,
            geocode_warning=geocode_warning,
        )
        self.pending_address.discard(chat_id)
        lines = [f"Адрес сохранён: {point.geo_summary()}"]
        if result:
            lines.append(
                f"Координаты найдены ({result.source}): {result.lat:.5f}, {result.lon:.5f}."
            )
        elif warning:
            lines.append(warning)
        lines.append("Вызовите /search или /basket.")
        self.send_message(chat_id, "\n".join(lines))

    def handle_basket(self, chat_id: int) -> None:
        self.send_typing(chat_id)
        self.send_message(chat_id, "Собираю корзину по сервисам…")
        text = build_basket_markdown(chat_id=chat_id)
        self.send_message(chat_id, text)

    def handle_search(self, chat_id: int, query: str) -> None:
        q = query.strip()
        if not q:
            self.send_message(
                chat_id,
                "Укажите запрос: /search молоко 1.5% или /item молоко 1.5%",
            )
            return
        self.send_typing(chat_id)
        self.send_message(chat_id, f"Ищу «{q}» по Samokat, Lavka, VkusVill…")
        text = build_search_markdown(q, chat_id=chat_id)
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
            try:
                self.save_location_pin(
                    chat_id, float(loc["latitude"]), float(loc["longitude"])
                )
            except Exception as exc:
                self._reply_error(chat_id, exc)
            return

        text = (message.get("text") or "").strip()
        if not text:
            return

        cmd, args = parse_bot_command(text)

        if cmd == "/ping":
            self.handle_ping(chat_id)
            return
        if cmd == "/start":
            self.handle_start(chat_id)
            return
        if cmd == "/address":
            if args:
                try:
                    self.save_address_text(chat_id, args)
                except Exception as exc:
                    self._reply_error(chat_id, exc)
            else:
                self.handle_address_prompt(chat_id)
            return
        if cmd == "/basket":
            try:
                self.handle_basket(chat_id)
            except Exception as exc:
                self._reply_error(chat_id, exc)
            return
        if cmd in ("/search", "/item"):
            try:
                self.handle_search(chat_id, args)
            except Exception as exc:
                self._reply_error(chat_id, exc)
            return

        if chat_id in self.pending_address and cmd is None:
            try:
                self.save_address_text(chat_id, text)
            except Exception as exc:
                self._reply_error(chat_id, exc)

    def _dispatch_update(self, update: dict[str, Any]) -> None:
        try:
            self.handle_update(update)
        except Exception as exc:
            chat_id = None
            msg = update.get("message") or update.get("edited_message") or {}
            chat = msg.get("chat") or {}
            if chat.get("id") is not None:
                chat_id = int(chat["id"])
            if chat_id is not None:
                self._reply_error(chat_id, exc)
            else:
                logger.exception(
                    "failed to handle update %s", update.get("update_id")
                )

    def run_polling(self, *, timeout: int = 30) -> None:
        logger.info("Connecting to Telegram (getMe)…")
        try:
            me = self._api("getMe", timeout=(8.0, 20.0))
            logger.info(
                "Polling started as @%s build=%s (long poll %ss — пауза без логов нормальна)",
                me.get("username"),
                BOT_BUILD,
                timeout,
            )
        except Exception as exc:
            logger.warning("getMe failed: %s — polling anyway", exc)
            logger.info("Polling started build=%s", BOT_BUILD)
        drop = os.environ.get("EGROCERY_DROP_PENDING", "1").strip().lower()
        drop_pending = drop not in ("0", "false", "no")
        while True:
            params: dict[str, Any] = {"timeout": timeout}
            if self.offset is not None:
                params["offset"] = self.offset
            elif drop_pending:
                params["drop_pending_updates"] = True
                drop_pending = False
            url = TELEGRAM_API.format(token=self.token, method="getUpdates")
            req = urllib.request.Request(
                url,
                data=json.dumps(params).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            read_timeout = float(timeout) + 15.0
            try:
                with urllib.request.urlopen(
                    req, timeout=(10.0, read_timeout)
                ) as resp:
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
                threading.Thread(
                    target=self._dispatch_update,
                    args=(update,),
                    daemon=True,
                    name=f"egrocery-update-{update.get('update_id')}",
                ).start()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )
    print("egrocery bot: starting…", flush=True)
    token = get_bot_token()
    if not token:
        raise SystemExit(
            "EGROCERY_BOT_TOKEN is not set (env or JOB_AGENT_STORE/internal/secrets.env)."
        )
    print("egrocery bot: token loaded, opening long poll to Telegram…", flush=True)
    TelegramBot(token).run_polling()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
