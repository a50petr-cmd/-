from __future__ import annotations

import logging
import os
from typing import Protocol

from egrocery.concurrent_util import run_parallel

from egrocery.cache import TtlCache
from egrocery.clients import lavka as lavka_client
from egrocery.clients import samokat as samokat_client
from egrocery.delivery_point import DeliveryPoint
from egrocery.http_client import ProviderHttpError
from egrocery.models import Basket
from egrocery.offers import Offer, filter_offers_for_query, pick_cheapest_offer
from egrocery.table import PLACEHOLDER
from egrocery.vkusvill_mcp import search_products as vkusvill_search

logger = logging.getLogger(__name__)

_search_cache: TtlCache[list[Offer]] = TtlCache()


class ProviderClient(Protocol):
    service_id: str

    def search_offers(self, point: DeliveryPoint, query: str, *, limit: int = 10) -> list[Offer]:
        ...


class VkusVillClient:
    service_id = "vkusvill"

    def search_offers(
        self, point: DeliveryPoint, query: str, *, limit: int = 10
    ) -> list[Offer]:
        _ = point
        return vkusvill_search(query, limit=limit)


class LavkaClient:
    service_id = "yandex_lavka"

    def search_offers(
        self, point: DeliveryPoint, query: str, *, limit: int = 10
    ) -> list[Offer]:
        if not point.has_coordinates():
            raise ProviderHttpError("Lavka: нужны lat/lon точки доставки")
        assert point.lat is not None and point.lon is not None
        return lavka_client.search_offers(point.lat, point.lon, query, limit=limit)


class SamokatClient:
    service_id = "samokat"

    def search_offers(
        self, point: DeliveryPoint, query: str, *, limit: int = 10
    ) -> list[Offer]:
        if not point.has_coordinates():
            raise ProviderHttpError("Samokat: нужны lat/lon точки доставки")
        assert point.lat is not None and point.lon is not None
        return samokat_client.search_offers(point.lat, point.lon, query, limit=limit)


CLIENTS: dict[str, ProviderClient] = {
    "samokat": SamokatClient(),
    "yandex_lavka": LavkaClient(),
    "vkusvill": VkusVillClient(),
}


def _cache_key(point: DeliveryPoint, service: str, query: str) -> str:
    chat = point.chat_id if point.chat_id is not None else "none"
    lat = f"{point.lat:.5f}" if point.lat is not None else "na"
    lon = f"{point.lon:.5f}" if point.lon is not None else "na"
    return f"{chat}|{service}|{lat}|{lon}|{query.strip().lower()}"


def search_offers_cached(
    point: DeliveryPoint, service: str, query: str, *, limit: int = 10
) -> tuple[list[Offer], str | None]:
    client = CLIENTS.get(service)
    if not client:
        return [], f"Неизвестный сервис {service}"
    key = _cache_key(point, service, query)
    cached = _search_cache.get(key)
    if cached is not None:
        return cached, None
    try:
        offers = client.search_offers(point, query, limit=limit)
    except ProviderHttpError as exc:
        logger.warning("%s search failed: %s", service, exc)
        return [], str(exc)
    except Exception as exc:
        logger.exception("%s search error", service)
        return [], f"{service}: {exc}"
    _search_cache.set(key, offers)
    return offers, None


def _provider_timeout_sec() -> float:
    raw = os.environ.get("EGROCERY_PROVIDER_TIMEOUT_SEC", "8").strip()
    try:
        return max(3.0, float(raw))
    except ValueError:
        return 8.0


def _basket_wall_timeout_sec(item_count: int) -> float:
    raw = os.environ.get("EGROCERY_BASKET_MAX_SEC", "40").strip()
    try:
        cap = max(15.0, float(raw))
    except ValueError:
        cap = 40.0
    per_item = _provider_timeout_sec() + 2.0
    return min(cap, per_item * max(1, item_count))


def search_all_providers(
    point: DeliveryPoint, query: str, *, limit: int = 10
) -> dict[str, tuple[list[Offer], str | None]]:
    services = [s for s in point.services_enabled if s in CLIENTS]
    if not services:
        return {}
    wall = _provider_timeout_sec() + 5.0
    jobs = {
        s: (lambda svc=s: search_offers_cached(point, svc, query, limit=limit))
        for s in services
    }
    raw = run_parallel(jobs, max_workers=min(3, len(services)), wall_timeout_sec=wall)
    out: dict[str, tuple[list[Offer], str | None]] = {}
    for service in services:
        val = raw.get(service)
        if val is None:
            out[service] = [], f"{service}: таймаут или ошибка"
        else:
            out[service] = val
    return out


def _format_cell(offer: Offer | None) -> str:
    if not offer:
        return PLACEHOLDER
    return offer.display_price()


def fetch_prices_for_service(
    point: DeliveryPoint, basket: Basket, service: str
) -> dict[str, str]:
    cells: dict[str, str] = {item.id: PLACEHOLDER for item in basket.items}
    if not basket.items:
        return cells
    wall = _basket_wall_timeout_sec(len(basket.items))

    def one(item_id: str, query: str) -> tuple[str, str]:
        offers, _err = search_offers_cached(point, service, query, limit=8)
        filtered, _rel = filter_offers_for_query(offers, query)
        best, _ = pick_cheapest_offer(filtered)
        return item_id, _format_cell(best)

    jobs = {
        item.id: (lambda i=item: one(i.id, i.query)) for item in basket.items
    }
    raw = run_parallel(jobs, max_workers=min(4, len(basket.items)), wall_timeout_sec=wall)
    for item_id, val in raw.items():
        if val is not None:
            cells[item_id] = val[1]
    return cells


def fetch_prices_samokat(point: DeliveryPoint, basket: Basket) -> dict[str, str]:
    logger.info(
        "fetch_prices_samokat: city=%s lat=%s lon=%s chat_id=%s",
        point.city,
        point.lat,
        point.lon,
        point.chat_id,
    )
    return fetch_prices_for_service(point, basket, "samokat")


def fetch_prices_lavka(point: DeliveryPoint, basket: Basket) -> dict[str, str]:
    logger.info(
        "fetch_prices_lavka: city=%s lat=%s lon=%s chat_id=%s",
        point.city,
        point.lat,
        point.lon,
        point.chat_id,
    )
    return fetch_prices_for_service(point, basket, "yandex_lavka")


def fetch_prices_vkusvill(point: DeliveryPoint, basket: Basket) -> dict[str, str]:
    logger.info(
        "fetch_prices_vkusvill: city=%s lat=%s lon=%s chat_id=%s",
        point.city,
        point.lat,
        point.lon,
        point.chat_id,
    )
    return fetch_prices_for_service(point, basket, "vkusvill")


PROVIDER_FETCHERS = {
    "samokat": fetch_prices_samokat,
    "yandex_lavka": fetch_prices_lavka,
    "vkusvill": fetch_prices_vkusvill,
}


def fetch_all_provider_prices(
    point: DeliveryPoint, basket: Basket
) -> dict[str, dict[str, str]]:
    keys = list(PROVIDER_FETCHERS.keys())
    wall = _basket_wall_timeout_sec(len(basket.items)) + 5.0
    jobs = {
        key: (lambda k=key: (k, PROVIDER_FETCHERS[k](point, basket))) for key in keys
    }
    raw = run_parallel(jobs, max_workers=3, wall_timeout_sec=wall)
    out: dict[str, dict[str, str]] = {}
    for key in keys:
        val = raw.get(key)
        if val is None:
            out[key] = {item.id: PLACEHOLDER for item in basket.items}
        else:
            out[key] = val[1]
    return out
