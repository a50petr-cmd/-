from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests
from requests.exceptions import ReadTimeout

from price_bot.telegram_bot import TelegramBot


def test_send_message_retries_on_read_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = TelegramBot("123456789:TestToken")
    attempts = {"n": 0}

    def fake_post(url: str, json: dict, timeout: float) -> MagicMock:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ReadTimeout("timed out")
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"ok": True, "result": {}}
        return resp

    sleeps: list[float] = []
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr("price_bot.telegram_bot.time.sleep", lambda s: sleeps.append(s))

    bot.send_message(42, "hello")

    assert attempts["n"] == 3
    assert sleeps == [1.0, 2.0]
