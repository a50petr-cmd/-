from __future__ import annotations

import json
import re
from typing import Any

from price_bot.http_client import get_http_client
from price_bot.models import Platform, ProductListing
from price_bot.platforms.base import MarketplaceClient


class FetchError(RuntimeError):
    pass


def _kopecks_to_rub(value: int | None) -> int | None:
    if value is None:
        return None
    return int(round(value / 100))


def _wb_product_url(nm: int | str) -> str:
    return f"https://www.wildberries.ru/catalog/{nm}/detail.aspx"


class WildberriesClient(MarketplaceClient):
    platform = Platform.WILDBERRIES

    def fetch_product(self, product_id: str, url: str) -> ProductListing:
        client = get_http_client()
        nm = int(product_id)
        api_urls = [
            "https://card.wb.ru/cards/v2/detail",
            "https://card.wb.ru/cards/v1/detail",
        ]
        last_status = None
        for api in api_urls:
            try:
                data = client.get_json(
                    api,
                    params={
                        "appType": 1,
                        "curr": "rub",
                        "dest": -1257786,
                        "spp": 30,
                        "nm": nm,
                    },
                )
            except Exception as exc:  # noqa: BLE001 — aggregate marketplace errors
                last_status = str(exc)
                continue
            products = data.get("data", {}).get("products") or data.get("products") or []
            if not products:
                continue
            p = products[0]
            price = p.get("salePriceU") or p.get("priceU") or p.get("extended", {}).get("basicPriceU")
            return ProductListing(
                platform=self.platform,
                product_id=str(p.get("id", nm)),
                title=(p.get("name") or "").strip() or f"Wildberries {nm}",
                price_rub=_kopecks_to_rub(price),
                url=url or _wb_product_url(nm),
                barcode=str(p.get("vendorCode") or "") or None,
            )
        raise FetchError(
            f"Wildberries: не удалось получить карточку (возможна блокировка или неверный артикул). {last_status or ''}"
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
            )
        except Exception as exc:  # noqa: BLE001
            raise FetchError(f"Wildberries search: {exc}") from exc

        products: list[dict[str, Any]] = data.get("data", {}).get("products") or []
        out: list[ProductListing] = []
        for p in products[:limit]:
            nm = p.get("id")
            if not nm:
                continue
            price = p.get("salePriceU") or p.get("priceU")
            out.append(
                ProductListing(
                    platform=self.platform,
                    product_id=str(nm),
                    title=(p.get("name") or "").strip(),
                    price_rub=_kopecks_to_rub(price),
                    url=_wb_product_url(nm),
                )
            )
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
