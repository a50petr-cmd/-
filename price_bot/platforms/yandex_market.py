from __future__ import annotations

import json
import re
from html import unescape
from typing import Any

from price_bot.http_client import get_http_client
from price_bot.models import Platform, ProductListing
from price_bot.platforms.base import MarketplaceClient
from price_bot.platforms.wildberries import FetchError


def _extract_next_data(html: str) -> dict[str, Any] | None:
    m = re.search(
        r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.I,
    )
    if not m:
        return None
    try:
        return json.loads(unescape(m.group(1)))
    except json.JSONDecodeError:
        return None


def _walk(node: Any, titles: list[str], prices: list[int]) -> None:
    if isinstance(node, dict):
        for key in ("title", "name", "productName"):
            val = node.get(key)
            if isinstance(val, str) and len(val) > 5:
                titles.append(val)
        for key in ("price", "value", "minPrice", "priceValue"):
            val = node.get(key)
            if isinstance(val, (int, float)) and val > 0:
                prices.append(int(val))
            elif isinstance(val, dict) and "value" in val:
                try:
                    prices.append(int(val["value"]))
                except (TypeError, ValueError):
                    pass
        for v in node.values():
            _walk(v, titles, prices)
    elif isinstance(node, list):
        for item in node:
            _walk(item, titles, prices)


class YandexMarketClient(MarketplaceClient):
    platform = Platform.YANDEX_MARKET

    def fetch_product(self, product_id: str, url: str) -> ProductListing:
        client = get_http_client()
        target = url or f"https://market.yandex.ru/product--/-/{product_id}"
        try:
            resp = client.get(target)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise FetchError(f"Яндекс Маркет: {exc}") from exc

        if "не робот" in resp.text.lower() or "captcha" in resp.text.lower():
            raise FetchError("Яндекс Маркет: требуется капча (запрос с сервера заблокирован).")

        data = _extract_next_data(resp.text)
        titles: list[str] = []
        prices: list[int] = []
        if data:
            _walk(data, titles, prices)
        title = titles[0] if titles else f"Яндекс Маркет {product_id}"
        price = min(prices) if prices else None
        return ProductListing(
            platform=self.platform,
            product_id=product_id,
            title=title,
            price_rub=price,
            url=target,
        )

    def search_products(self, query: str, limit: int = 3) -> list[ProductListing]:
        client = get_http_client()
        try:
            resp = client.get(
                "https://market.yandex.ru/search",
                params={"text": query},
            )
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise FetchError(f"Яндекс Маркет search: {exc}") from exc

        if "не робот" in resp.text.lower():
            raise FetchError("Яндекс Маркет search: капча.")

        data = _extract_next_data(resp.text)
        out: list[ProductListing] = []
        seen: set[str] = set()
        if data:
            blob = json.dumps(data, ensure_ascii=False)

            def add(pid: str, title: str | None = None) -> None:
                if pid in seen or len(out) >= limit:
                    return
                seen.add(pid)
                out.append(
                    ProductListing(
                        platform=self.platform,
                        product_id=pid,
                        title=title or f"Яндекс Маркет {pid}",
                        price_rub=None,
                        url=f"https://market.yandex.ru/product--/-/{pid}",
                    )
                )

            for match in re.finditer(
                r'"productId"\s*:\s*"?(\d{5,})"?.*?"(?:title|name)"\s*:\s*"([^"]{5,200})"',
                blob,
            ):
                add(match.group(1), match.group(2))
                if len(out) >= limit:
                    break
            if not out:
                for pid in re.findall(r"/product--[^/]+/(\d{5,})", blob):
                    add(pid)
                    if len(out) >= limit:
                        break
        return out
