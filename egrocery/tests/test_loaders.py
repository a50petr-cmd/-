from __future__ import annotations

from pathlib import Path

from egrocery.loaders import active_service_columns, load_basket, load_location


def test_load_location_and_basket(tmp_path: Path) -> None:
    loc = tmp_path / "loc.yaml"
    loc.write_text(
        """
city: Электросталь
region: Московская область
country: RU
services_enabled:
  - samokat
  - yandex_lavka
  - vkusvill
services_deferred:
  - ozon_fresh
""".strip(),
        encoding="utf-8",
    )
    basket = tmp_path / "basket.yaml"
    basket.write_text(
        """
name: test-basket
items:
  - id: milk
    label: Молоко
    query: молоко
    unit_hint: 1 л
""".strip(),
        encoding="utf-8",
    )
    location = load_location(loc)
    assert location.city == "Электросталь"
    assert location.services_deferred == ("ozon_fresh",)
    loaded = load_basket(basket)
    assert loaded.name == "test-basket"
    assert len(loaded.items) == 1
    assert loaded.items[0].query == "молоко"
    cols = active_service_columns(location)
    assert cols == ("samokat", "yandex_lavka", "vkusvill")
