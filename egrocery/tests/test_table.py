from __future__ import annotations

from egrocery.models import Basket, BasketItem, Location
from egrocery.table import PLACEHOLDER, format_basket_table


def test_format_basket_table_markdown() -> None:
    location = Location(
        city="Электросталь",
        region="Московская область",
        country="RU",
        services_enabled=("samokat", "yandex_lavka", "vkusvill"),
        services_deferred=("ozon_fresh",),
    )
    basket = Basket(
        name="starter",
        items=(
            BasketItem(id="milk", label="Молоко 1,5%", query="m", unit_hint="1 л"),
            BasketItem(id="eggs", label="Яйца", query="e"),
        ),
    )
    text = format_basket_table(location, basket)
    assert "| Позиция | Samokat | Lavka | VkusVill |" in text
    assert f"| Молоко 1,5% (1 л) | {PLACEHOLDER} | {PLACEHOLDER} | {PLACEHOLDER} |" in text
    assert "Elektrostal" in text or "Samokat and Yandex Lavka" in text
    assert "ozon_fresh" in text
