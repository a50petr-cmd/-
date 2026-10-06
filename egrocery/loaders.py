from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from egrocery.models import Basket, BasketItem, Location

SERVICE_COLUMN_ORDER = ("samokat", "yandex_lavka", "vkusvill")

SERVICE_DISPLAY: dict[str, str] = {
    "samokat": "Samokat",
    "yandex_lavka": "Lavka",
    "vkusvill": "VkusVill",
}


def _require_mapping(data: Any, context: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{context}: expected mapping, got {type(data).__name__}")
    return data


def load_location(path: Path) -> Location:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc = _require_mapping(raw, str(path))
    enabled = doc.get("services_enabled") or []
    deferred = doc.get("services_deferred") or []
    if not isinstance(enabled, list) or not isinstance(deferred, list):
        raise ValueError(f"{path}: services_* must be lists")
    return Location(
        city=str(doc.get("city", "")),
        region=str(doc.get("region", "")),
        country=str(doc.get("country", "RU")),
        services_enabled=tuple(str(s) for s in enabled),
        services_deferred=tuple(str(s) for s in deferred),
        address_note=(str(doc["address_note"]) if doc.get("address_note") else None),
        metro=(str(doc["metro"]) if doc.get("metro") else None),
    )


def load_basket(path: Path) -> Basket:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc = _require_mapping(raw, str(path))
    items_raw = doc.get("items") or []
    if not isinstance(items_raw, list):
        raise ValueError(f"{path}: items must be a list")
    items: list[BasketItem] = []
    for idx, entry in enumerate(items_raw):
        item = _require_mapping(entry, f"{path} items[{idx}]")
        items.append(
            BasketItem(
                id=str(item["id"]),
                label=str(item["label"]),
                query=str(item.get("query") or item["label"]),
                unit_hint=(str(item["unit_hint"]) if item.get("unit_hint") else None),
            )
        )
    return Basket(name=str(doc.get("name", path.stem)), items=tuple(items))


def active_service_columns(location: Location) -> tuple[str, ...]:
    enabled = set(location.services_enabled)
    return tuple(s for s in SERVICE_COLUMN_ORDER if s in enabled)
