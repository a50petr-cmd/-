from __future__ import annotations

import json
import re
from typing import Any

from price_bot.http_client import get_http_client
from price_bot.models import Platform, ProductListing
from price_bot.platforms.base import MarketplaceClient

WB_MARKETPLACE_HEADERS = {
    "Referer": "https://www.wildberries.ru/",
    "Origin": "https://www.wildberries.ru",
}

# Common dest values (Moscow / default catalog regions).
_WB_DEST_PARAMS = (-1257786, -1029256, 123585, -364001)


class FetchError(RuntimeError):
    pass


def _kopecks_to_rub(value: int | None) -> int | None:
    if value is None:
        return None
    return int(round(value / 100))


def _wb_product_url(nm: int | str) -> str:
    return f"https://www.wildberries.ru/catalog/{nm}/detail.aspx"


def _listing_from_wb_product(p: dict[str, Any], nm: int | str, url: str) -> ProductListing:
    price = p.get("salePriceU") or p.get("priceU") or p.get("extended", {}).get("basicPriceU")
    return ProductListing(
        platform=Platform.WILDBERRIES,
        product_id=str(p.get("id", nm)),
        title=(p.get("name") or p.get("imt_name") or "").strip() or f"Wildberries {nm}",
        price_rub=_kopecks_to_rub(price if isinstance(price, int) else None),
        url=url or _wb_product_url(nm),
        barcode=str(p.get("vendorCode") or "") or None,
    )


def _find_product_node(obj: Any, nm: int) -> dict[str, Any] | None:
    """Walk arbitrary JSON (e.g. __NEXT_DATA__) for a product dict matching nm."""
    if isinstance(obj, dict):
        pid = obj.get("id") or obj.get("nm") or obj.get("nmId")
        if pid is not None and str(pid) == str(nm):
            if any(k in obj for k in ("salePriceU", "priceU", "name", "imt_name")):
                return obj
        for v in obj.values():
            found = _find_product_node(v, nm)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_product_node(item, nm)
            if found:
                return found
    return None


def _parse_product_html(html: str, nm: int, url: str) -> ProductListing | None:
    m = re.search(
        r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if m:
        try:
            data = json.loads(m.group(1))
            node = _find_product_node(data, nm)
            if node:
                return _listing_from_wb_product(node, nm, url)
        except json.JSONDecodeError:
            pass

    # Embedded catalog JSON fragments (older or alternate layouts).
    for block in re.findall(r"\{[^{}]{0,8000}?\}", html):
        if f'"id":{nm}' not in block and f'"nm":{nm}' not in block and f'"nmId":{nm}' not in block:
            continue
        try:
            obj = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            node = _find_product_node(obj, nm)
            if node:
                return _listing_from_wb_product(node, nm, url)

    name_m = re.search(r'"name"\s*:\s*"((?:\\.|[^"\\])*)"', html)
    price_m = re.search(r'"(?:salePriceU|priceU)"\s*:\s*(\d+)', html)
    if name_m or price_m:
        title = name_m.group(1).encode().decode("unicode_escape") if name_m else f"Wildberries {nm}"
        price_rub = _kopecks_to_rub(int(price_m.group(1))) if price_m else None
        return ProductListing(
            platform=Platform.WILDBERRIES,
            product_id=str(nm),
            title=title.strip() or f"Wildberries {nm}",
            price_rub=price_rub,
            url=url,
        )
    return None


class WildberriesClient(MarketplaceClient):
    platform = Platform.WILDBERRIES

    def fetch_product(self, product_id: str, url: str) -> ProductListing:
        client = get_http_client()
        nm = int(product_id)
        page_url = url or _wb_product_url(nm)
        api_urls = [
            "https://card.wb.ru/cards/v2/detail",
            "https://card.wb.ru/cards/v1/detail",
        ]
        last_status: str | None = None
        for api in api_urls:
            for dest in _WB_DEST_PARAMS:
                try:
                    data = client.get_json(
                        api,
                        params={
                            "appType": 1,
                            "curr": "rub",
                            "dest": dest,
                            "spp": 30,
                            "nm": nm,
                        },
                        headers=WB_MARKETPLACE_HEADERS,
                    )
                except Exception as exc:  # noqa: BLE001 — aggregate marketplace errors
                    last_status = str(exc)
                    continue
                products = data.get("data", {}).get("products") or data.get("products") or []
                if not products:
                    continue
                return _listing_from_wb_product(products[0], nm, page_url)

        try:
            resp = client.get(page_url, headers=WB_MARKETPLACE_HEADERS)
            if resp.status_code == 200:
                listing = _parse_product_html(resp.text, nm, page_url)
                if listing:
                    return listing
            last_status = last_status or f"HTML {resp.status_code}"
        except Exception as exc:  # noqa: BLE001
            last_status = last_status or str(exc)

        raise FetchError(
            "Wildberries: не удалось получить карточку (возможна блокировка API 403 — "
            "обновите код и проверьте с домашнего IP). "
            f"{last_status or ''}".strip()
        )

    def search_products(self, query: str, limit: int = 3) -> list[ProductListing]:
        client = get_http_client()
        try:
            data = client.get_json(
                "https://search.wb.ru/exactmatch/ru/common/v5/search",
                params={
                    "appType": 1,
                    "curr": "rub",
                    "dest": -1257786,
                    "query": query,
                    "resultset": "catalog",
                    "sort": "popular",
                    "spp": 30,
                    "suppressSpellcheck": False,
                },
                headers=WB_MARKETPLACE_HEADERS,
            )
        except Exception as exc:  # noqa: BLE001
            raise FetchError(f"Wildberries search: {exc}") from exc

        products: list[dict[str, Any]] = data.get("data", {}).get("products") or []
        out: list[ProductListing] = []
        for p in products[:limit]:
            nm = p.get("id")
            if not nm:
                continue
            out.append(_listing_from_wb_product(p, nm, _wb_product_url(nm)))
        return out

    @staticmethod
    def parse_search_html(html: str, limit: int = 3) -> list[ProductListing]:
        """Fallback when JSON search API is blocked."""
        ids = re.findall(r"/catalog/(\d+)/detail", html)
        seen: set[str] = set()
        out: list[ProductListing] = []
        for pid in ids:
            if pid in seen:
                continue
            seen.add(pid)
            out.append(
                ProductListing(
                    platform=Platform.WILDBERRIES,
                    product_id=pid,
                    title=f"Wildberries {pid}",
                    price_rub=None,
                    url=_wb_product_url(pid),
                )
            )
            if len(out) >= limit:
                break
        return out
