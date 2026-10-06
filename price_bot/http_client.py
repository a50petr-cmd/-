from __future__ import annotations

import time
from typing import Any

import requests

from price_bot.config import REQUEST_MIN_INTERVAL, USER_AGENT


class HttpClient:
    """Shared session with rate limiting and a mobile User-Agent."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/html, */*",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            }
        )
        self._last_request_at = 0.0

    def _wait_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < REQUEST_MIN_INTERVAL:
            time.sleep(REQUEST_MIN_INTERVAL - elapsed)

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 20.0,
    ) -> requests.Response:
        self._wait_rate_limit()
        merged = dict(self._session.headers)
        if headers:
            merged.update(headers)
        resp = self._session.get(url, params=params, headers=merged, timeout=timeout)
        self._last_request_at = time.monotonic()
        return resp

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        resp = self.get(url, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()


_client: HttpClient | None = None


def get_http_client() -> HttpClient:
    global _client
    if _client is None:
        _client = HttpClient()
    return _client
