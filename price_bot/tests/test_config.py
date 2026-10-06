from __future__ import annotations

import os
from pathlib import Path

import pytest

from price_bot.config import get_bot_token, load_dotenv_file


def test_load_dotenv_strips_crlf_from_value(tmp_path: Path) -> None:
    env_file = tmp_path / "secrets.env"
    env_file.write_bytes(b'PRICE_BOT_TOKEN=123:ABCdef\r\nTELEGRAM_BOT_TOKEN=999:job\r\n')
    loaded = load_dotenv_file(env_file)
    assert loaded["PRICE_BOT_TOKEN"] == "123:ABCdef"
    assert loaded["TELEGRAM_BOT_TOKEN"] == "999:job"


def test_get_bot_token_no_fallback_when_price_key_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / "internal" / "secrets.env"
    env_file.parent.mkdir()
    env_file.write_text(
        "PRICE_BOT_TOKEN=\nTELEGRAM_BOT_TOKEN=123456789:FallbackToken\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("PRICE_BOT_TOKEN", raising=False)
    monkeypatch.setenv("JOB_AGENT_STORE", str(tmp_path))
    assert get_bot_token() is None


def test_get_bot_token_uses_price_when_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / "internal" / "secrets.env"
    env_file.parent.mkdir()
    env_file.write_text(
        "PRICE_BOT_TOKEN=111:Price\r\nTELEGRAM_BOT_TOKEN=222:Job\r\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("PRICE_BOT_TOKEN", raising=False)
    monkeypatch.setenv("JOB_AGENT_STORE", str(tmp_path))
    assert get_bot_token() == "111:Price"
