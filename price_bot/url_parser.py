from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

from price_bot.models import Platform

_OZON_HOSTS = ("ozon.ru", "www.ozon.ru", "m.ozon.ru")
_WB_HOSTS = ("wildberries.ru", "www.wildberries.ru", "m.wildberries.ru")
_YM_HOSTS = ("market.yandex.ru", "m.market.yandex.ru")


@dataclass(frozen=True)
class ParsedProductUrl:
    platform: Platform
    product_id: str
    canonical_url: str


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def fallback_search_query(url: str, product_id: str) -> str:
    """Search text when the source listing could not be loaded."""
    raw = url.strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    path = unquote(urlparse(raw).path or "")
    m = re.search(r"/product/([\w\-]+)-\d{5,}", path, re.I)
    if m:
        slug = m.group(1).replace("-", " ").strip()
        if len(slug) >= 3:
            return slug
    return product_id


def parse_product_url(url: str) -> ParsedProductUrl:
    raw = url.strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = _host(raw)
    path = unquote(parsed.path or "")

    if host in _OZON_HOSTS or host.endswith(".ozon.ru"):
        return _parse_ozon(parsed, path, raw)
    if host in _WB_HOSTS or host.endswith(".wildberries.ru"):
        return _parse_wildberries(parsed, path, raw)
    if host in _YM_HOSTS or "market.yandex" in host:
        return _parse_yandex(parsed, path, raw)

    raise ValueError(
        "Поддерживаются только ссылки Ozon, Wildberries и Яндекс Маркет."
    )


def _parse_ozon(parsed, path: str, raw: str) -> ParsedProductUrl:
    # /product/slug-123456789/ or /product/123456789/
    m = re.search(r"/product/(?:[\w\-]+-)?(\d{5,})", path, re.I)
    if not m:
        qs = parse_qs(parsed.query)
        if "product_id" in qs:
            pid = qs["product_id"][0]
            return ParsedProductUrl(
                Platform.OZON, pid, f"https://www.ozon.ru/product/-{pid}/"
            )
        raise ValueError("Не удалось извлечь ID товара Ozon из ссылки.")
    pid = m.group(1)
    canonical = f"https://www.ozon.ru/product/-{pid}/"
    return ParsedProductUrl(Platform.OZON, pid, canonical)


def _parse_wildberries(parsed, path: str, raw: str) -> ParsedProductUrl:
    m = re.search(r"/catalog/(\d+)/", path)
    if not m:
        qs = parse_qs(parsed.query)
        for key in ("nm", "id"):
            if key in qs:
                pid = qs[key][0]
                return ParsedProductUrl(
                    Platform.WILDBERRIES,
                    pid,
                    f"https://www.wildberries.ru/catalog/{pid}/detail.aspx",
                )
        raise ValueError("Не удалось извлечь артикул Wildberries из ссылки.")
    pid = m.group(1)
    return ParsedProductUrl(
        Platform.WILDBERRIES,
        pid,
        f"https://www.wildberries.ru/catalog/{pid}/detail.aspx",
    )


def _parse_yandex(parsed, path: str, raw: str) -> ParsedProductUrl:
    # /product--name/123456789 or /product/123456789
    m = re.search(r"/product(?:--[^/]+)?/(\d{5,})", path, re.I)
    if not m:
        m = re.search(r"/card/[^/]+/(\d{5,})", path, re.I)
    if not m:
        qs = parse_qs(parsed.query)
        if "sku" in qs:
            pid = qs["sku"][0]
            return ParsedProductUrl(
                Platform.YANDEX_MARKET,
                pid,
                f"https://market.yandex.ru/product--/-/{pid}",
            )
        raise ValueError("Не удалось извлечь ID товара Яндекс Маркета из ссылки.")
    pid = m.group(1)
    return ParsedProductUrl(
        Platform.YANDEX_MARKET,
        pid,
        f"https://market.yandex.ru/product--/-/{pid}",
    )
