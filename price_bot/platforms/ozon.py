from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import quote

from price_bot.http_client import get_http_client
from price_bot.models import Platform, ProductListing
from price_bot.platforms.base import MarketplaceClient
from price_bot.platforms.wildberries import FetchError

OZON_MARKETPLACE_HEADERS = {
    "Referer": "https://www.ozon.ru/",
    "Origin": "https://www.ozon.ru",
}

_OZON_DESKTOP_UA = os.environ.get(
    "PRICE_BOT_OZON_DESKTOP_UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
)

_COMPOSER_API = "https://www.ozon.ru/api/composer-api.bx/page/json/v2"


def _extract_price_rub(text: str | int | float | None) -> int | None:
    if text is None:
        return None
    if isinstance(text, (int, float)):
        val = int(text)
        # Ozon sometimes uses kopecks in raw JSON fragments.
        if val > 10_000_000:
            return None
        if val > 500_000 and val % 100 == 0:
            return val // 100
        return val
    digits = re.sub(r"[^\d]", "", str(text))
    return int(digits) if digits else None


def _walk_widgets(node: Any, titles: list[str], prices: list[int]) -> None:
    if isinstance(node, dict):
        if "title" in node and isinstance(node["title"], str) and len(node["title"]) > 3:
            titles.append(node["title"])
        for key in ("price", "finalPrice", "cardPrice", "originalPrice"):
            if key in node:
                p = _extract_price_rub(node[key])
                if p:
                    prices.append(p)
        if "cellTrackingInfo" in node and isinstance(node["cellTrackingInfo"], dict):
            u = node["cellTrackingInfo"].get("product") or node["cellTrackingInfo"]
            if isinstance(u, dict):
                p = _extract_price_rub(u.get("price"))
                if p:
                    prices.append(p)
        for v in node.values():
            _walk_widgets(v, titles, prices)
    elif isinstance(node, list):
        for item in node:
            _walk_widgets(item, titles, prices)


def _canonical_page_url(url: str, product_id: str) -> str:
    base = (url or f"https://www.ozon.ru/product/-{product_id}/").split("?", 1)[0]
    if not base.endswith("/"):
        base += "/"
    return base


def _user_agent_attempts() -> list[str | None]:
    if os.environ.get("PRICE_BOT_OZON_USE_DESKTOP", "").lower() in ("1", "true", "yes"):
        return [_OZON_DESKTOP_UA]
    custom = os.environ.get("PRICE_BOT_USER_AGENT")
    if custom:
        return [custom, _OZON_DESKTOP_UA]
    return [None, _OZON_DESKTOP_UA]


def _request_headers(user_agent: str | None) -> dict[str, str]:
    headers = dict(OZON_MARKETPLACE_HEADERS)
    if user_agent:
        headers["User-Agent"] = user_agent
    return headers


def _get_composer_json(client, page_path: str) -> tuple[Any | None, str | None]:
    last_error: str | None = None
    for ua in _user_agent_attempts():
        try:
            resp = client.get(
                _COMPOSER_API,
                params={"url": page_path},
                headers=_request_headers(ua),
            )
            if resp.status_code == 403:
                last_error = "composer-api HTTP 403"
                continue
            if resp.status_code >= 400:
                last_error = f"composer-api HTTP {resp.status_code}"
                continue
            return resp.json(), None
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
    return None, last_error


def _listing_from_composer(data: Any, product_id: str, url: str) -> ProductListing:
    titles: list[str] = []
    prices: list[int] = []
    _walk_widgets(data, titles, prices)
    title = next((t for t in titles if len(t) > 5), f"Ozon {product_id}")
    price = min(prices) if prices else None
    return ProductListing(
        platform=Platform.OZON,
        product_id=product_id,
        title=title,
        price_rub=price,
        url=url,
    )


def _parse_ld_json_product(html: str) -> tuple[str | None, int | None]:
    title: str | None = None
    prices: list[int] = []
    for block in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        try:
            payload = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        nodes = payload if isinstance(payload, list) else [payload]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = node.get("@type") or ""
            types = node_type if isinstance(node_type, list) else [node_type]
            if not any(t == "Product" for t in types):
                continue
            if isinstance(node.get("name"), str) and len(node["name"]) > 3:
                title = node["name"]
            offers = node.get("offers")
            if isinstance(offers, dict):
                p = _extract_price_rub(offers.get("price") or offers.get("lowPrice"))
                if p:
                    prices.append(p)
            elif isinstance(offers, list):
                for offer in offers:
                    if isinstance(offer, dict):
                        p = _extract_price_rub(offer.get("price") or offer.get("lowPrice"))
                        if p:
                            prices.append(p)
    return title, min(prices) if prices else None


def _parse_html_price_patterns(html: str) -> tuple[str | None, int | None]:
    title: str | None = None
    prices: list[int] = []

    og = re.search(
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if og:
        title = og.group(1).strip()

    for key in ("finalPrice", "cardPrice", "originalPrice", "price"):
        for m in re.finditer(rf'"{key}"\s*:\s*"?(\d[\d\s]*)"?', html):
            p = _extract_price_rub(m.group(1))
            if p and 10 <= p <= 5_000_000:
                prices.append(p)

    for m in re.finditer(r'data-state=["\'](\{.*?\})["\']', html):
        blob = m.group(1)
        try:
            state = json.loads(blob.replace("&quot;", '"'))
        except json.JSONDecodeError:
            continue
        walk_titles: list[str] = []
        walk_prices: list[int] = []
        _walk_widgets(state, walk_titles, walk_prices)
        if walk_titles and not title:
            title = walk_titles[0]
        prices.extend(walk_prices)

    return title, min(prices) if prices else None


def parse_product_html(html: str, product_id: str, url: str) -> ProductListing | None:
    title, price = _parse_ld_json_product(html)
    if price is None or not title:
        t2, p2 = _parse_html_price_patterns(html)
        title = title or t2
        price = price if price is not None else p2
    if not title and not price:
        return None
    return ProductListing(
        platform=Platform.OZON,
        product_id=product_id,
        title=(title or f"Ozon {product_id}").strip(),
        price_rub=price,
        url=url,
    )


def _fetch_product_html(client, page_url: str) -> tuple[str | None, str | None]:
    last_error: str | None = None
    for ua in _user_agent_attempts():
        try:
            resp = client.get(page_url, headers=_request_headers(ua))
            if resp.status_code == 403:
                last_error = "HTML HTTP 403"
                continue
            if resp.status_code >= 400:
                last_error = f"HTML HTTP {resp.status_code}"
                continue
            return resp.text, None
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
    return None, last_error


def parse_search_html(html: str, limit: int = 3) -> list[ProductListing]:
    out: list[ProductListing] = []
    seen: set[str] = set()
    blob_prices: dict[str, list[int]] = {}

    for m in re.finditer(
        r'/product/(?:[\w\-]+-)?(\d{5,})/?["\'][^"\']{0,400}?"price"\s*:\s*"?(\d[\d\s]*)"?',
        html,
    ):
        pid, raw = m.group(1), m.group(2)
        p = _extract_price_rub(raw)
        if p:
            blob_prices.setdefault(pid, []).append(p)

    for pid in re.findall(r"/product/(?:[\w\-]+-)?(\d{5,})", html):
        if pid in seen:
            continue
        seen.add(pid)
        price = min(blob_prices[pid]) if pid in blob_prices else None
        out.append(
            ProductListing(
                platform=Platform.OZON,
                product_id=pid,
                title=f"Ozon {pid}",
                price_rub=price,
                url=f"https://www.ozon.ru/product/-{pid}/",
            )
        )
        if len(out) >= limit:
            break
    return out


class OzonClient(MarketplaceClient):
    platform = Platform.OZON

    def fetch_product(self, product_id: str, url: str) -> ProductListing:
        client = get_http_client()
        page_url = _canonical_page_url(url, product_id)
        page_path = f"/product/-{product_id}/"

        data, composer_err = _get_composer_json(client, page_path)
        if data is not None:
            listing = _listing_from_composer(data, product_id, page_url)
            if listing.price_rub is not None or len(listing.title) > 12:
                return listing

        html, html_err = _fetch_product_html(client, page_url)
        if html:
            parsed = parse_product_html(html, product_id, page_url)
            if parsed and (parsed.price_rub is not None or parsed.title):
                if data is not None and parsed.price_rub is None:
                    composer_listing = _listing_from_composer(data, product_id, page_url)
                    if composer_listing.price_rub is None and composer_listing.title:
                        parsed.title = composer_listing.title
                return parsed

        detail = " — ".join(x for x in (composer_err, html_err) if x)
        raise FetchError(
            "Ozon: не удалось получить карточку (composer-api часто отвечает 403 — "
            "обновите код; при необходимости задайте PRICE_BOT_OZON_USE_DESKTOP=1). "
            f"{detail}".strip()
        )

    def search_products(self, query: str, limit: int = 3) -> list[ProductListing]:
        client = get_http_client()
        search_path = f"/search/?text={quote(query)}&from_global=true"
        data, composer_err = _get_composer_json(client, search_path)

        out: list[ProductListing] = []
        if data is not None:
            out = self._collect_from_composer(data, limit)

        if out:
            return out[:limit]

        search_url = f"https://www.ozon.ru/search/?text={quote(query)}&from_global=true"
        html, html_err = _fetch_product_html(client, search_url)
        if html:
            html_hits = parse_search_html(html, limit)
            if html_hits:
                return html_hits

        detail = " — ".join(x for x in (composer_err, html_err) if x)
        raise FetchError(f"Ozon search: не удалось выполнить поиск. {detail}".strip())

    def _collect_from_composer(self, data: Any, limit: int) -> list[ProductListing]:
        out: list[ProductListing] = []
        seen: set[str] = set()

        def collect(node: Any) -> None:
            if len(out) >= limit:
                return
            if isinstance(node, dict):
                link = node.get("link") or node.get("action", {}).get("link")
                title = node.get("title") or node.get("name")
                price_raw = node.get("price") or node.get("finalPrice")
                if link and isinstance(link, str) and "/product/" in link:
                    m = re.search(r"/product/(?:[\w\-]+-)?(\d{5,})", link)
                    if m:
                        pid = m.group(1)
                        if pid not in seen:
                            seen.add(pid)
                            out.append(
                                ProductListing(
                                    platform=self.platform,
                                    product_id=pid,
                                    title=str(title or f"Ozon {pid}"),
                                    price_rub=_extract_price_rub(price_raw),
                                    url=f"https://www.ozon.ru/product/-{pid}/",
                                )
                            )
                for v in node.values():
                    collect(v)
            elif isinstance(node, list):
                for item in node:
                    collect(item)

        collect(data)
        if out:
            return out[:limit]

        blob = json.dumps(data, ensure_ascii=False)
        for pid in re.findall(r"/product/(?:[\w\-]+-)?(\d{5,})", blob):
            if pid in seen:
                continue
            seen.add(pid)
            out.append(
                ProductListing(
                    platform=self.platform,
                    product_id=pid,
                    title=f"Ozon {pid}",
                    price_rub=None,
                    url=f"https://www.ozon.ru/product/-{pid}/",
                )
            )
            if len(out) >= limit:
                break
        return out
