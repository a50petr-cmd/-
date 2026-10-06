from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from egrocery.geocode import geocode_address_with_warning
from egrocery.loaders import load_location
from egrocery.models import Location


@dataclass(frozen=True)
class DeliveryPoint:
    """Merged delivery context: default location YAML + optional user overrides."""

    city: str
    region: str
    country: str
    services_enabled: tuple[str, ...]
    services_deferred: tuple[str, ...]
    address_text: str | None = None
    lat: float | None = None
    lon: float | None = None
    address_note: str | None = None
    metro: str | None = None
    chat_id: int | None = None
    updated_at: str | None = None
    geocode_warning: str | None = None

    def has_coordinates(self) -> bool:
        return self.lat is not None and self.lon is not None

    def geo_summary(self) -> str:
        parts: list[str] = []
        if self.address_text:
            parts.append(self.address_text)
        elif self.address_note:
            parts.append(self.address_note)
        if self.has_coordinates():
            parts.append(f"({self.lat:.5f}, {self.lon:.5f})")
        if not parts:
            return f"{self.city}, {self.region}"
        return ", ".join(parts)


def delivery_point_from_location(location: Location) -> DeliveryPoint:
    return DeliveryPoint(
        city=location.city,
        region=location.region,
        country=location.country,
        services_enabled=location.services_enabled,
        services_deferred=location.services_deferred,
        address_note=location.address_note,
        metro=location.metro,
    )


def merge_delivery_point(
    location: Location,
    *,
    address_text: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    chat_id: int | None = None,
    updated_at: str | None = None,
    city: str | None = None,
    geocode_warning: str | None = None,
) -> DeliveryPoint:
    base = delivery_point_from_location(location)
    resolved_city = (city or base.city or "Электросталь").strip() or "Электросталь"
    return DeliveryPoint(
        city=resolved_city,
        region=base.region,
        country=base.country,
        services_enabled=base.services_enabled,
        services_deferred=base.services_deferred,
        address_text=address_text if address_text is not None else base.address_text,
        lat=lat if lat is not None else base.lat,
        lon=lon if lon is not None else base.lon,
        address_note=base.address_note,
        metro=base.metro,
        chat_id=chat_id,
        updated_at=updated_at,
        geocode_warning=geocode_warning,
    )


def user_yaml_path(store_root: Path, chat_id: int) -> Path:
    return store_root / "internal" / "egrocery" / "users" / f"{chat_id}.yaml"


def _require_mapping(data: Any, context: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{context}: expected mapping, got {type(data).__name__}")
    return data


def load_user_delivery_doc(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    return _require_mapping(raw, str(path))


def save_user_delivery_doc(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def load_user_delivery_point(
    store_root: Path,
    chat_id: int,
    location_path: Path,
) -> DeliveryPoint | None:
    path = user_yaml_path(store_root, chat_id)
    doc = load_user_delivery_doc(path)
    if doc is None:
        return None
    location = load_location(location_path)
    lat = doc.get("lat")
    lon = doc.get("lon")
    return merge_delivery_point(
        location,
        address_text=(str(doc["address_text"]) if doc.get("address_text") else None),
        lat=(float(lat) if lat is not None else None),
        lon=(float(lon) if lon is not None else None),
        chat_id=chat_id,
        updated_at=(str(doc["updated_at"]) if doc.get("updated_at") else None),
        city=(str(doc["city"]) if doc.get("city") else None),
        geocode_warning=(
            str(doc["geocode_warning"]) if doc.get("geocode_warning") else None
        ),
    )


def save_user_delivery_point(
    store_root: Path,
    chat_id: int,
    *,
    address_text: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    city: str | None = None,
    geocode_warning: str | None = None,
) -> DeliveryPoint:
    location_path = store_root / "docs" / "e-grocery-location.yaml"
    if location_path.is_file():
        location = load_location(location_path)
    else:
        location = Location(
            city="Электросталь",
            region="Московская область",
            country="RU",
            services_enabled=("samokat", "yandex_lavka", "vkusvill"),
            services_deferred=("ozon_fresh",),
        )
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    existing = load_user_delivery_doc(user_yaml_path(store_root, chat_id)) or {}
    resolved_city = (
        city or existing.get("city") or location.city or "Электросталь"
    ).strip() or "Электросталь"
    doc: dict[str, Any] = {
        "chat_id": chat_id,
        "city": resolved_city,
        "updated_at": now,
    }
    if address_text is not None:
        doc["address_text"] = address_text
    elif existing.get("address_text"):
        doc["address_text"] = existing["address_text"]
    if lat is not None:
        doc["lat"] = lat
    elif existing.get("lat") is not None:
        doc["lat"] = existing["lat"]
    if lon is not None:
        doc["lon"] = lon
    elif existing.get("lon") is not None:
        doc["lon"] = existing["lon"]
    if geocode_warning is not None:
        if geocode_warning:
            doc["geocode_warning"] = geocode_warning
    elif existing.get("geocode_warning"):
        doc["geocode_warning"] = existing["geocode_warning"]
    save_user_delivery_doc(user_yaml_path(store_root, chat_id), doc)
    return merge_delivery_point(
        location,
        address_text=address_text,
        lat=lat,
        lon=lon,
        chat_id=chat_id,
        updated_at=now,
        city=resolved_city,
        geocode_warning=geocode_warning,
    )


def ensure_delivery_point_geocoded(
    store_root: Path,
    chat_id: int,
    point: DeliveryPoint,
    location_path: Path,
) -> DeliveryPoint:
    """If user has address text but no coordinates, retry geocoding once."""
    if point.has_coordinates() or not point.address_text:
        return point
    location = load_location(location_path)
    result, warning = geocode_address_with_warning(
        point.address_text,
        city=point.city or location.city,
        region=location.region,
        country=location.country,
    )
    if result is None:
        return point
    return save_user_delivery_point(
        store_root,
        chat_id,
        address_text=point.address_text,
        lat=result.lat,
        lon=result.lon,
        city=result.city or point.city,
        geocode_warning=warning if warning else "",
    )


def resolve_delivery_point(
    location_path: Path,
    *,
    chat_id: int | None = None,
    store_root: Path | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> DeliveryPoint:
    location = load_location(location_path)
    point = delivery_point_from_location(location)
    if store_root is not None and chat_id is not None:
        user_point = load_user_delivery_point(store_root, chat_id, location_path)
        if user_point is not None:
            point = user_point
    if lat is not None and lon is not None:
        point = merge_delivery_point(
            location,
            address_text=point.address_text,
            lat=lat,
            lon=lon,
            chat_id=point.chat_id,
            updated_at=point.updated_at,
            city=point.city,
            geocode_warning=point.geocode_warning,
        )
    return point
