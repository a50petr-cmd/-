from __future__ import annotations

import os
import time
from typing import Any

import requests

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class ProviderHttpError(Exception):
    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def get_http_user_agent() -> str:
    return os.environ.get("EGROCERY_HTTP_USER_AGENT", "").strip() or DEFAULT_USER_AGENT


class HttpClient:
    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": get_http_user_agent(),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            }
        )
        self._last_at = 0.0
        self._min_interval = float(os.environ.get("EGROCERY_HTTP_MIN_INTERVAL", "0.3"))

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_at
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 20.0,
    ) -> requests.Response:
        self._wait()
        merged = dict(self._session.headers)
        if headers:
            merged.update(headers)
        resp = self._session.request(
            method.upper(),
            url,
            params=params,
            json=json,
            headers=merged,
            timeout=timeout,
        )
        self._last_at = time.monotonic()
        return resp

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 20.0,
    ) -> Any:
        resp = self.request("GET", url, params=params, headers=headers, timeout=timeout)
        if resp.status_code == 403:
            raise ProviderHttpError(
                "HTTP 403 — доступ с этого IP/без cookies заблокирован",
                status=403,
            )
        resp.raise_for_status()
        return resp.json()

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
        timeout: float = 20.0,
    ) -> Any:
        resp = self.request(
            "POST", url, json=payload, headers=headers, timeout=timeout
        )
        if resp.status_code in (401, 403):
            raise ProviderHttpError(
                f"HTTP {resp.status_code} — нужна авторизация/cookies или домашний IP",
                status=resp.status_code,
            )
        resp.raise_for_status()
        return resp.json()


_client: HttpClient | None = None


def shared_http_client() -> HttpClient:
    global _client
    if _client is None:
        _client = HttpClient()
    return _client
