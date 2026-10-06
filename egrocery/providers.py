from __future__ import annotations

import logging

from egrocery.delivery_point import DeliveryPoint
from egrocery.models import Basket
from egrocery.table import PLACEHOLDER

logger = logging.getLogger(__name__)


def _log_geo(provider: str, point: DeliveryPoint) -> None:
    logger.info(
        "%s: geo city=%s lat=%s lon=%s chat_id=%s",
        provider,
        point.city,
        point.lat,
        point.lon,
        point.chat_id,
    )


def fetch_prices_samokat(point: DeliveryPoint, basket: Basket) -> dict[str, str]:
    _log_geo("fetch_prices_samokat", point)
    return {item.id: PLACEHOLDER for item in basket.items}


def fetch_prices_lavka(point: DeliveryPoint, basket: Basket) -> dict[str, str]:
    _log_geo("fetch_prices_lavka", point)
    return {item.id: PLACEHOLDER for item in basket.items}


def fetch_prices_vkusvill(point: DeliveryPoint, basket: Basket) -> dict[str, str]:
    _log_geo("fetch_prices_vkusvill", point)
    return {item.id: PLACEHOLDER for item in basket.items}


PROVIDER_FETCHERS = {
    "samokat": fetch_prices_samokat,
    "yandex_lavka": fetch_prices_lavka,
    "vkusvill": fetch_prices_vkusvill,
}


def fetch_all_provider_prices(
    point: DeliveryPoint, basket: Basket
) -> dict[str, dict[str, str]]:
    return {key: fn(point, basket) for key, fn in PROVIDER_FETCHERS.items()}
