from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

from egrocery.http_client import ProviderHttpError, shared_http_client
from egrocery.offers import Offer

_API_WEB = os.environ.get("SAMOKAT_API_BASE", "https://api-web.samokat.ru").rstrip("/")
_API_MOBILE = os.environ.get("SAMOKAT_MOBILE_API_BASE", "https://api.samokat.ru").rstrip(
    "/"
)


def _to_price(value: Any) -> float | None:
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    # Samokat often returns kopecks
    if num > 1000:
        return num / 100.0
    return num


def _resolve_showcase_id(lat: float, lon: float) -> str | None:
    client = shared_http_client()
    url = f"{_API_MOBILE}/showcase/showcases"
    try:
        data = client.get_json(url, params={"version": "0", "lat": lat, "lon": lon})
    except ProviderHttpError:
        data = None
    except Exception:
        data = None
    if isinstance(data, dict):
        for key in ("showcaseId", "showcase_id", "id"):
            if data.get(key):
                return str(data[key])
        showcases = data.get("showcases")
        if isinstance(showcases, list) and showcases:
            first = showcases[0]
            if isinstance(first, dict) and first.get("id"):
                return str(first["id"])
    # api-web fallback
    try:
        data2 = client.get_json(
            f"{_API_WEB}/v2/showcases",
            params={"lat": lat, "lon": lon},
        )
    except Exception:
        return None
    if isinstance(data2, list) and data2:
        item = data2[0]
        if isinstance(item, dict) and item.get("id"):
            return str(item["id"])
    if isinstance(data2, dict) and data2.get("id"):
        return str(data2["id"])
    return None


def search_offers(lat: float, lon: float, query: str, *, limit: int = 10) -> list[Offer]:
    showcase_id = _resolve_showcase_id(lat, lon)
    client = shared_http_client()
    paths: list[tuple[str, dict[str, Any] | None]] = []
    if showcase_id:
        paths.append(
            (
                f"{_API_WEB}/v2/showcases/{showcase_id}/products/search",
                {"query": query, "limit": limit},
            )
        )
        paths.append(
            (
                f"{_API_WEB}/v2/search/products",
                {"query": query, "showcaseId": showcase_id, "limit": limit},
            )
        )
    paths.append(
        (
            f"{_API_WEB}/v2/search/products",
            {"query": query, "lat": lat, "lon": lon, "limit": limit},
        )
    )

    last_error: ProviderHttpError | None = None
    for url, params in paths:
        try:
            data = client.get_json(url, params=params, timeout=8.0)
        except ProviderHttpError as exc:
            last_error = exc
            if exc.status == 403:
                raise exc
            continue
        except Exception:
            continue
        products = _extract_products(data)
        if products:
            return _map_products(products, limit)
    if last_error:
        raise last_error
    raise ProviderHttpError(
        "Samokat: поиск недоступен (403/geo) — попробуйте с домашнего IP в Электростали"
    )


def _extract_products(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        for key in ("products", "items", "result", "data"):
            val = data.get(key)
            if isinstance(val, list):
                return [p for p in val if isinstance(p, dict)]
            if isinstance(val, dict):
                inner = val.get("products") or val.get("items")
                if isinstance(inner, list):
                    return [p for p in inner if isinstance(p, dict)]
    if isinstance(data, list):
        return [p for p in data if isinstance(p, dict)]
    return []


def _map_products(products: list[dict[str, Any]], limit: int) -> list[Offer]:
    offers: list[Offer] = []
    for item in products[:limit]:
        price = _to_price(
            item.get("price")
            or item.get("currentPrice")
            or item.get("discountPrice")
            or item.get("salePrice")
        )
        if price is None:
            continue
        name = str(item.get("name") or item.get("title") or "").strip()
        if not name:
            continue
        product_id = str(item.get("id") or item.get("productId") or "")
        slug = item.get("slug") or product_id
        url = item.get("url") or item.get("webUrl")
        if not url and slug:
            url = f"https://samokat.ru/product/{quote(str(slug))}"
        offers.append(
            Offer(
                service="samokat",
                product_name=name,
                price_rub=price,
                url=str(url) if url else None,
                quantity_label=str(item.get("specification") or item.get("weight") or ""),
                product_id=product_id or None,
            )
        )
    return offers
