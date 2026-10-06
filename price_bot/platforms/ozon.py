from __future__ import annotations

import json
import re
from typing import Any

from price_bot.http_client import get_http_client
from price_bot.models import Platform, ProductListing
from price_bot.platforms.base import MarketplaceClient
from price_bot.platforms.wildberries import FetchError


def _extract_price_rub(text: str | int | float | None) -> int | None:
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text)
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


class OzonClient(MarketplaceClient):
    platform = Platform.OZON

    def fetch_product(self, product_id: str, url: str) -> ProductListing:
        client = get_http_client()
        page_path = f"/product/-{product_id}/"
        try:
            data = client.get_json(
                "https://www.ozon.ru/api/composer-api.bx/page/json/v2",
                params={"url": page_path},
            )
        except Exception as exc:  # noqa: BLE001
            raise FetchError(f"Ozon: {exc}") from exc

        titles: list[str] = []
        prices: list[int] = []
        _walk_widgets(data, titles, prices)
        title = next((t for t in titles if len(t) > 5), f"Ozon {product_id}")
        price = min(prices) if prices else None
        return ProductListing(
            platform=self.platform,
            product_id=product_id,
            title=title,
            price_rub=price,
            url=url or f"https://www.ozon.ru/product/-{product_id}/",
        )

    def search_products(self, query: str, limit: int = 3) -> list[ProductListing]:
        client = get_http_client()
        try:
            data = client.get_json(
                "https://www.ozon.ru/api/composer-api.bx/page/json/v2",
                params={"url": f"/search/?text={query}&from_global=true"},
            )
        except Exception as exc:  # noqa: BLE001
            raise FetchError(f"Ozon search: {exc}") from exc

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

        # Regex fallback on serialized JSON
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
