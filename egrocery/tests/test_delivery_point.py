from __future__ import annotations

from pathlib import Path

import yaml

from egrocery.delivery_point import (
    load_user_delivery_doc,
    load_user_delivery_point,
    save_user_delivery_point,
    user_yaml_path,
)
from egrocery.loaders import load_location


def _write_location(store: Path) -> Path:
    docs = store / "docs"
    docs.mkdir(parents=True)
    path = docs / "e-grocery-location.yaml"
    path.write_text(
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
    return path


def test_save_and_load_user_yaml(tmp_path: Path) -> None:
    store = tmp_path / "store"
    store.mkdir()
    loc_path = _write_location(store)
    chat_id = 4242
    save_user_delivery_point(
        store,
        chat_id,
        address_text="Электросталь, тестовая 1",
        lat=55.789,
        lon=38.456,
        city="Электросталь",
    )
    path = user_yaml_path(store, chat_id)
    assert path.is_file()
    doc = load_user_delivery_doc(path)
    assert doc is not None
    assert doc["chat_id"] == chat_id
    assert doc["address_text"] == "Электросталь, тестовая 1"
    assert doc["lat"] == 55.789
    assert doc["lon"] == 38.456
    assert doc["city"] == "Электросталь"
    assert "updated_at" in doc

    point = load_user_delivery_point(store, chat_id, loc_path)
    assert point is not None
    assert point.address_text == "Электросталь, тестовая 1"
    assert point.lat == 55.789
    assert point.chat_id == chat_id


def test_save_location_preserves_address_text(tmp_path: Path) -> None:
    store = tmp_path / "store"
    store.mkdir()
    loc_path = _write_location(store)
    chat_id = 99
    save_user_delivery_point(store, chat_id, address_text="ул. Красная 1")
    save_user_delivery_point(store, chat_id, lat=55.1, lon=38.2)
    doc = yaml.safe_load(user_yaml_path(store, chat_id).read_text(encoding="utf-8"))
    assert doc["address_text"] == "ул. Красная 1"
    assert doc["lat"] == 55.1
    point = load_user_delivery_point(store, chat_id, loc_path)
    assert point is not None
    assert "Красная" in point.geo_summary()
