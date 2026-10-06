from __future__ import annotations

from unittest.mock import patch

from egrocery.delivery_point import DeliveryPoint
from egrocery.models import Basket, BasketItem
from egrocery.offers import Offer
from egrocery.providers import fetch_prices_vkusvill, search_offers_cached
from egrocery.table import PLACEHOLDER


def _point() -> DeliveryPoint:
    return DeliveryPoint(
        city="Электросталь",
        region="МО",
        country="RU",
        services_enabled=("vkusvill",),
        services_deferred=(),
        lat=55.78,
        lon=38.44,
        chat_id=280846801,
    )


def test_fetch_basket_uses_cheapest_search_result() -> None:
    basket = Basket(
        name="test",
        items=(
            BasketItem(id="milk", label="Молоко", query="молоко 1.5%"),
        ),
    )
    fake_offers = [
        Offer(service="vkusvill", product_name="Дорогое", price_rub=200.0),
        Offer(service="vkusvill", product_name="Дешёвое", price_rub=80.0),
    ]
    with patch(
        "egrocery.providers.vkusvill_search", return_value=fake_offers
    ):
        cells = fetch_prices_vkusvill(_point(), basket)
    assert cells["milk"] == "80 ₽"


def test_search_offers_cached_returns_provider_error() -> None:
    with patch(
        "egrocery.providers.vkusvill_search",
        side_effect=RuntimeError("boom"),
    ):
        offers, err = search_offers_cached(_point(), "vkusvill", "хлеб")
    assert offers == []
    assert err is not None


def test_samokat_missing_coords_keeps_placeholder() -> None:
    point = DeliveryPoint(
        city="Электросталь",
        region="МО",
        country="RU",
        services_enabled=("samokat",),
        services_deferred=(),
    )
    basket = Basket(
        name="t",
        items=(BasketItem(id="x", label="X", query="x"),),
    )
    from egrocery.providers import fetch_prices_samokat

    cells = fetch_prices_samokat(point, basket)
    assert cells["x"] == PLACEHOLDER
