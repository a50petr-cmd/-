from __future__ import annotations

import html
import os
import re
from typing import Any

from egrocery.clients.lavka_session import resolve_lavka_session
from egrocery.http_client import ProviderHttpError, shared_http_client
from egrocery.offers import Offer

_CSRF_RE = re.compile(r'"csrfToken"\s*:\s*"([^"]+)"')
_BASE = "https://lavka.yandex.ru"


def _web_city() -> str:
    return os.environ.get("YANDEX_LAVKA_WEB_CITY", "213").strip() or "213"


def _clean_title(text: Any) -> str:
    return html.unescape(re.sub(r"</?notr>", "", str(text or "").replace("\xad", "")))


def _to_price(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace("\xa0", "").replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return None


def _ensure_csrf(session_headers: dict[str, str]) -> str | None:
    preset = os.environ.get("YANDEX_LAVKA_CSRF_TOKEN", "").strip()
    if preset:
        return preset
    client = shared_http_client()
    resp = client.request("GET", f"{_BASE}/", headers=session_headers, timeout=25.0)
    if resp.status_code in (401, 403):
        raise ProviderHttpError(
            f"Lavka HTTP {resp.status_code} — обновите cookies (bootstrap или браузер)",
            status=resp.status_code,
        )
    match = _CSRF_RE.search(resp.text)
    return match.group(1) if match else None


def search_offers(lat: float, lon: float, query: str, *, limit: int = 10) -> list[Offer]:
    lavka = resolve_lavka_session()
    session_headers = {
        "Cookie": lavka.cookie_header,
        "Origin": _BASE,
        "Referer": f"{_BASE}/",
        "X-Requested-With": "XMLHttpRequest",
    }
    csrf = lavka.csrf_token or _ensure_csrf(session_headers)
    headers = {
        **session_headers,
        "Content-Type": "application/json",
        "X-Lavka-Web-Locale": "ru-RU",
        "X-Lavka-Web-City": _web_city(),
    }
    if csrf:
        headers["X-CSRF-Token"] = csrf
    body = {
        "depotType": "regular",
        "currencySign": "₽",
        "position": {"location": [lon, lat]},
        "text": query,
        "productsLimit": limit,
        "subcategoriesLimit": 0,
        "useRetail": True,
        "source": "manual_input",
    }
    client = shared_http_client()
    resp = client.request(
        "POST",
        f"{_BASE}/api/v1/providers/search/v3/lavka",
        json=body,
        headers=headers,
        timeout=25.0,
    )
    if resp.status_code in (401, 403):
        from egrocery.clients.lavka_session import bootstrap_guest_session

        try:
            lavka = bootstrap_guest_session()
        except ProviderHttpError:
            raise ProviderHttpError(
                f"Lavka HTTP {resp.status_code} — вставьте YANDEX_LAVKA_COOKIE из браузера (lavka.yandex.ru)",
                status=resp.status_code,
            ) from None
        headers["Cookie"] = lavka.cookie_header
        if lavka.csrf_token:
            headers["X-CSRF-Token"] = lavka.csrf_token
        resp = client.request(
            "POST",
            f"{_BASE}/api/v1/providers/search/v3/lavka",
            json=body,
            headers=headers,
            timeout=25.0,
        )
        if resp.status_code in (401, 403):
            raise ProviderHttpError(
                f"Lavka HTTP {resp.status_code} — нужна сессия Yandex из браузера",
                status=resp.status_code,
            )
    if resp.status_code >= 400:
        raise ProviderHttpError(f"Lavka HTTP {resp.status_code}", status=resp.status_code)
    raw = resp.json()
    if isinstance(raw, dict) and raw.get("type") == "captcha":
        raise ProviderHttpError(
            "Lavka: captcha — один раз скопируйте Cookie из браузера в secrets.env"
        )
    products = raw.get("cacheProducts") if isinstance(raw, dict) else None
    products = products if isinstance(products, list) else []
    offers: list[Offer] = []
    for item in products[:limit]:
        if not isinstance(item, dict):
            continue
        price = _to_price(item.get("currentPrice") or item.get("price"))
        if price is None:
            continue
        slug = item.get("deepLink") or item.get("slug")
        url = f"{_BASE}/good/{slug}" if slug else None
        offers.append(
            Offer(
                service="yandex_lavka",
                product_name=_clean_title(item.get("title") or item.get("name")),
                price_rub=price,
                url=url,
                quantity_label=str(item.get("amount") or item.get("weight") or ""),
                product_id=str(item.get("id") or ""),
            )
        )
    return offers
