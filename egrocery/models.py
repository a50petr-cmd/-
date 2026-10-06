from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    city: str
    region: str
    country: str
    services_enabled: tuple[str, ...]
    services_deferred: tuple[str, ...]
    address_note: str | None = None
    metro: str | None = None


@dataclass(frozen=True)
class BasketItem:
    id: str
    label: str
    query: str
    unit_hint: str | None = None


@dataclass(frozen=True)
class Basket:
    name: str
    items: tuple[BasketItem, ...]
