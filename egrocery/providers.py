from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Protocol

from egrocery.cache import TtlCache
from egrocery.clients import lavka as lavka_client
from egrocery.clients import samokat as samokat_client
from egrocery.delivery_point import DeliveryPoint
from egrocery.http_client import ProviderHttpError
from egrocery.models import Basket
from egrocery.offers import Offer, pick_cheapest_offer
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
    raw = os.environ.get("EGROCERY_PROVIDER_TIMEOUT_SEC", "12").strip()
    try:
        return max(3.0, float(raw))
    except ValueError:
        return 12.0


def search_all_providers(
    point: DeliveryPoint, query: str, *, limit: int = 10
) -> dict[str, tuple[list[Offer], str | None]]:
    services = [s for s in point.services_enabled if s in CLIENTS]
    if not services:
        return {}
    timeout = _provider_timeout_sec()
    out: dict[str, tuple[list[Offer], str | None]] = {}
    with ThreadPoolExecutor(max_workers=min(3, len(services))) as pool:
        futures = {
            pool.submit(search_offers_cached, point, s, query, limit=limit): s
            for s in services
        }
        for fut in as_completed(futures, timeout=timeout + 2):
            service = futures[fut]
            try:
                out[service] = fut.result(timeout=1)
            except Exception as exc:
                logger.warning("%s parallel search failed: %s", service, exc)
                out[service] = [], f"{service}: таймаут или ошибка"
    for service in services:
        out.setdefault(service, ([], f"{service}: нет ответа"))
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
    timeout = _provider_timeout_sec()

    def one(item_id: str, query: str) -> tuple[str, str]:
        offers, _err = search_offers_cached(point, service, query, limit=8)
        best, _ = pick_cheapest_offer(offers)
        return item_id, _format_cell(best)

    with ThreadPoolExecutor(max_workers=min(4, len(basket.items))) as pool:
        futures = [
            pool.submit(one, item.id, item.query) for item in basket.items
        ]
        try:
            for fut in as_completed(futures, timeout=timeout * len(basket.items)):
                item_id, cell = fut.result(timeout=1)
                cells[item_id] = cell
        except Exception as exc:
            logger.warning("%s basket row fetch incomplete: %s", service, exc)
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
    timeout = _provider_timeout_sec() * max(1, len(basket.items))

    def run(key: str) -> tuple[str, dict[str, str]]:
        return key, PROVIDER_FETCHERS[key](point, basket)

    out: dict[str, dict[str, str]] = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(run, key): key for key in keys}
        try:
            for fut in as_completed(futures, timeout=timeout + 5):
                key, cells = fut.result(timeout=1)
                out[key] = cells
        except Exception as exc:
            logger.warning("basket provider fetch incomplete: %s", exc)
    for key in keys:
        out.setdefault(key, {item.id: PLACEHOLDER for item in basket.items})
    return out
