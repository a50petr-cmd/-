from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import requests
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import ReadTimeout, Timeout

from price_bot.compare import compare_url
from price_bot.config import get_bot_token, get_secrets_path, get_store_root
from price_bot.telegram_validate import verify_bot_token_getme
from price_bot.formatters import format_comparison_message
from price_bot.url_parser import parse_product_url

log = logging.getLogger(__name__)

CONNECT_TIMEOUT = 15
SEND_READ_TIMEOUT = float(os.environ.get("PRICE_BOT_SEND_TIMEOUT", "90"))
QUICK_SEND_READ_TIMEOUT = 30
LONG_POLL_SECONDS = int(os.environ.get("PRICE_BOT_LONG_POLL_SECONDS", "25"))

SEND_MAX_ATTEMPTS = 3

_TELEGRAM_API_BASE = os.environ.get(
    "PRICE_BOT_TELEGRAM_API_BASE", "https://api.telegram.org"
).rstrip("/")
API_BASE = f"{_TELEGRAM_API_BASE}/bot{{token}}/{{method}}"

SEND_NETWORK_ERRORS = (ReadTimeout, Timeout, RequestsConnectionError)

_TELEGRAM_SEND_USER_MSG = (
    "Не удалось отправить ответ в Telegram (сеть или таймаут). "
    "Попробуйте ещё раз через минуту."
)
_COMPARE_FAIL_USER_MSG = (
    "Не удалось получить цены. Попробуйте позже или отправьте другую ссылку."
)
_SEARCHING_MSG = "Ищу цены..."


class TelegramDeliveryError(Exception):
    """Telegram sendMessage failed after retries."""


class TelegramBot:
    def __init__(self, token: str) -> None:
        self.token = token
        self.offset: int | None = None
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="price-compare"
        )

    def _method_url(self, method: str) -> str:
        return API_BASE.format(token=self.token, method=method)

    def _post(
        self,
        method: str,
        payload: dict[str, Any],
        *,
        read_timeout: float,
    ) -> dict[str, Any]:
        url = self._method_url(method)
        resp = requests.post(
            url, json=payload, timeout=(CONNECT_TIMEOUT, read_timeout)
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data}")
        return data

    def _call_with_send_retry(
        self,
        method: str,
        payload: dict[str, Any],
        *,
        read_timeout: float = SEND_READ_TIMEOUT,
    ) -> dict[str, Any]:
        url = self._method_url(method)
        timeout = (CONNECT_TIMEOUT, read_timeout)
        last_exc: Exception | None = None
        for attempt in range(SEND_MAX_ATTEMPTS):
            try:
                resp = requests.post(url, json=payload, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
                if not data.get("ok"):
                    raise RuntimeError(f"Telegram API error: {data}")
                return data
            except SEND_NETWORK_ERRORS as exc:
                last_exc = exc
                log.warning(
                    "Telegram %s attempt %s/%s failed: %s",
                    method,
                    attempt + 1,
                    SEND_MAX_ATTEMPTS,
                    exc,
                )
                if attempt + 1 < SEND_MAX_ATTEMPTS:
                    time.sleep(2**attempt)
        assert last_exc is not None
        raise TelegramDeliveryError(str(last_exc)) from last_exc

    def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        read_timeout: float = SEND_READ_TIMEOUT,
    ) -> None:
        # Telegram limit 4096 chars
        chunk_size = 4000
        for i in range(0, len(text), chunk_size):
            self._call_with_send_retry(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": text[i : i + chunk_size],
                    "disable_web_page_preview": True,
                },
                read_timeout=read_timeout,
            )

    def _send_quick(self, chat_id: int | str, text: str) -> bool:
        """Immediate ack with shorter read timeout; returns False if all attempts fail."""
        try:
            self.send_message(chat_id, text, read_timeout=QUICK_SEND_READ_TIMEOUT)
            return True
        except TelegramDeliveryError as exc:
            log.error(
                "Telegram: не удалось отправить сообщение в чат %s после %s попыток "
                "(connect=%ss, read=%ss): %s",
                chat_id,
                SEND_MAX_ATTEMPTS,
                CONNECT_TIMEOUT,
                QUICK_SEND_READ_TIMEOUT,
                exc,
            )
            return False

    def _safe_send(self, chat_id: int | str, text: str) -> None:
        try:
            self.send_message(chat_id, text)
        except TelegramDeliveryError:
            log.exception("Telegram delivery failed for chat %s", chat_id)
            try:
                self.send_message(chat_id, _TELEGRAM_SEND_USER_MSG)
            except TelegramDeliveryError:
                log.error(
                    "Telegram: все попытки sendMessage исчерпаны для чата %s "
                    "(connect=%ss, read=%ss)",
                    chat_id,
                    CONNECT_TIMEOUT,
                    SEND_READ_TIMEOUT,
                )

    def _compare_and_reply(self, chat_id: int | str, url: str) -> None:
        try:
            result = compare_url(url)
            self._safe_send(chat_id, format_comparison_message(result))
        except ValueError as exc:
            self._safe_send(chat_id, f"Не удалось сравнить: {exc}")
        except Exception:  # noqa: BLE001
            log.exception("compare failed")
            self._safe_send(chat_id, _COMPARE_FAIL_USER_MSG)

    def get_updates(self, timeout: int | None = None) -> list[dict[str, Any]]:
        long_poll = LONG_POLL_SECONDS if timeout is None else timeout
        payload: dict[str, Any] = {"timeout": long_poll}
        if self.offset is not None:
            payload["offset"] = self.offset
        read_timeout = long_poll + 15
        data = self._post("getUpdates", payload, read_timeout=read_timeout)
        return data.get("result", [])

    def handle_text(self, chat_id: int | str, text: str) -> None:
        stripped = text.strip()
        try:
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
                self.send_message(
                    chat_id, "Нужна ссылка на товар (Ozon / WB / Яндекс Маркет)."
                )
                return

            try:
                parse_product_url(stripped)
            except ValueError as exc:
                self.send_message(chat_id, str(exc))
                return

            self._send_quick(chat_id, _SEARCHING_MSG)
            self._executor.submit(self._compare_and_reply, chat_id, stripped)
        except TelegramDeliveryError:
            log.error(
                "Telegram: handle_text не смог ответить в чат %s (сеть/таймаут)",
                chat_id,
            )

    def process_update(self, update: dict[str, Any]) -> None:
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return
        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        text = msg.get("text")
        if chat_id is None or not text:
            return
        try:
            self.handle_text(chat_id, text)
        except Exception:  # noqa: BLE001
            log.exception("process_update failed for chat %s", chat_id)

    def run_polling(self) -> None:
        log.info(
            "Starting Telegram long polling (long_poll=%ss, getUpdates read=%ss)",
            LONG_POLL_SECONDS,
            LONG_POLL_SECONDS + 15,
        )
        while True:
            try:
                updates = self.get_updates()
                for upd in updates:
                    self.offset = upd["update_id"] + 1
                    self.process_update(upd)
            except KeyboardInterrupt:
                log.info("Stopped by user")
                break
            except ReadTimeout:
                log.debug(
                    "getUpdates read timeout (long_poll=%ss); continuing",
                    LONG_POLL_SECONDS,
                )
            except Timeout as exc:
                log.warning("getUpdates timeout: %s; continuing polling", exc)
            except SEND_NETWORK_ERRORS as exc:
                log.warning("getUpdates network error: %s; retry in 3s", exc)
                time.sleep(3)
            except Exception as exc:  # noqa: BLE001
                log.warning("Polling error: %s", exc)
                time.sleep(3)
        self._executor.shutdown(wait=False)


def run_bot() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    token = get_bot_token()
    if not token:
        secrets_path = get_secrets_path()
        store_root = get_store_root()
        raise SystemExit(
            "Set PRICE_BOT_TOKEN (recommended) or TELEGRAM_BOT_TOKEN in env, "
            f"or add it to {secrets_path} "
            f"(store root: {store_root}; set JOB_AGENT_STORE or PRICE_BOT_STORE if needed)."
        )
    verify_bot_token_getme(token)
    TelegramBot(token).run_polling()
