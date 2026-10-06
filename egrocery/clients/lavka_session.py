from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

import requests

from egrocery.config import lavka_cookie_cache_path
from egrocery.http_client import ProviderHttpError, get_http_user_agent

logger = logging.getLogger(__name__)

_BASE = "https://lavka.yandex.ru"
_CSRF_RE = re.compile(r'"csrfToken"\s*:\s*"([^"]+)"')


@dataclass
class LavkaSession:
    cookie_header: str
    csrf_token: str | None = None


def _auto_cookie_enabled() -> bool:
    raw = os.environ.get("EGROCERY_LAVKA_AUTO_COOKIE", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _cookies_to_header(session: requests.Session) -> str:
    parts = [f"{k}={v}" for k, v in session.cookies.get_dict().items()]
    return "; ".join(parts)


def load_cached_session() -> LavkaSession | None:
    path = lavka_cookie_cache_path()
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None
    csrf: str | None = None
    cookie = text
    if "\n" in text:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for ln in lines:
            if ln.lower().startswith("csrf:"):
                csrf = ln.split(":", 1)[1].strip()
            elif ln.lower().startswith("cookie:"):
                cookie = ln.split(":", 1)[1].strip()
        if not cookie.startswith("=") and "cookie:" not in text.lower():
            cookie = lines[-1]
    if not cookie:
        return None
    return LavkaSession(cookie_header=cookie, csrf_token=csrf)


def save_cached_session(session: LavkaSession) -> None:
    path = lavka_cookie_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"cookie: {session.cookie_header}"]
    if session.csrf_token:
        lines.append(f"csrf: {session.csrf_token}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Lavka guest cookies saved to %s", path)


def bootstrap_guest_session() -> LavkaSession:
    """Fetch lavka.yandex.ru and collect Set-Cookie (no Yandex login)."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": get_http_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9",
        }
    )
    resp = session.get(_BASE + "/", timeout=(10.0, 25.0))
    if resp.status_code in (401, 403):
        raise ProviderHttpError(
            f"Lavka bootstrap HTTP {resp.status_code} — нужен YANDEX_LAVKA_COOKIE из браузера",
            status=resp.status_code,
        )
    resp.raise_for_status()
    cookie_header = _cookies_to_header(session)
    if not cookie_header:
        raise ProviderHttpError(
            "Lavka: не удалось получить cookies с главной — задайте YANDEX_LAVKA_COOKIE вручную"
        )
    csrf = None
    match = _CSRF_RE.search(resp.text)
    if match:
        csrf = match.group(1)
    lavka = LavkaSession(cookie_header=cookie_header, csrf_token=csrf)
    save_cached_session(lavka)
    return lavka


def resolve_lavka_session(*, force_bootstrap: bool = False) -> LavkaSession:
    from egrocery.config import get_lavka_cookie_override

    override = get_lavka_cookie_override()
    if override:
        return LavkaSession(cookie_header=override)

    if not force_bootstrap:
        cached = load_cached_session()
        if cached:
            return cached

    if not _auto_cookie_enabled():
        raise ProviderHttpError(
            "Lavka: не задан YANDEX_LAVKA_COOKIE и EGROCERY_LAVKA_AUTO_COOKIE=0"
        )

    return bootstrap_guest_session()
