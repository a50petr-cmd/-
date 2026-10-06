from __future__ import annotations

from egrocery.offers import Offer, pick_cheapest_offer


def test_pick_cheapest_by_unit_price_per_liter() -> None:
    offers = [
        Offer(
            service="vkusvill",
            product_name="Молоко 1 л",
            price_rub=100.0,
        ),
        Offer(
            service="samokat",
            product_name="Молоко 900 мл",
            price_rub=85.0,
        ),
    ]
    best, disclaimer = pick_cheapest_offer(offers)
    assert best is not None
    assert best.service == "samokat"
    assert disclaimer is None
    assert best.unit_price_rub is not None


def test_pick_cheapest_absolute_when_no_weight() -> None:
    offers = [
        Offer(service="a", product_name="Молоко", price_rub=120.0),
        Offer(service="b", product_name="Молоко", price_rub=99.0),
    ]
    best, disclaimer = pick_cheapest_offer(offers)
    assert best is not None
    assert best.price_rub == 99.0
    assert disclaimer is not None
