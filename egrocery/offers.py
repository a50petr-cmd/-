from __future__ import annotations

import re
from dataclasses import dataclass

_GRAMS_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(кг|г|g)\b", re.IGNORECASE
)
_LITERS_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(л|l|мл|ml)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class Offer:
    service: str
    product_name: str
    price_rub: float
    url: str | None = None
    unit_price_rub: float | None = None
    unit_basis: str | None = None  # e.g. "per_l", "per_kg"
    quantity_label: str | None = None
    product_id: str | None = None

    def display_price(self) -> str:
        if self.price_rub == int(self.price_rub):
            return f"{int(self.price_rub)} ₽"
        return f"{self.price_rub:.2f} ₽"


def _parse_amount(text: str) -> float | None:
    t = text.replace("\xa0", " ").replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)", t)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def infer_quantity_basis(*texts: str | None) -> tuple[float | None, str | None]:
    """Return (amount in base unit, basis) — liters or kg — from free text."""
    joined = " ".join(t for t in texts if t).lower()
    m = _LITERS_RE.search(joined)
    if m:
        value = float(m.group(1).replace(",", "."))
        unit = m.group(2).lower()
        if unit in ("мл", "ml"):
            return value / 1000.0, "per_l"
        return value, "per_l"
    m = _GRAMS_RE.search(joined)
    if m:
        value = float(m.group(1).replace(",", "."))
        unit = m.group(2).lower()
        if unit in ("г", "g"):
            return value / 1000.0, "per_kg"
        return value, "per_kg"
    return None, None


def enrich_unit_price(offer: Offer) -> Offer:
    if offer.unit_price_rub is not None:
        return offer
    amount, basis = infer_quantity_basis(
        offer.product_name, offer.quantity_label, offer.unit_basis
    )
    if amount and amount > 0:
        return Offer(
            service=offer.service,
            product_name=offer.product_name,
            price_rub=offer.price_rub,
            url=offer.url,
            unit_price_rub=offer.price_rub / amount,
            unit_basis=basis,
            quantity_label=offer.quantity_label,
            product_id=offer.product_id,
        )
    return offer


def pick_cheapest_offer(
    offers: list[Offer],
) -> tuple[Offer | None, str | None]:
    """Pick min unit price when comparable; else min absolute price + disclaimer."""
    if not offers:
        return None, None
    enriched = [enrich_unit_price(o) for o in offers]
    with_unit = [o for o in enriched if o.unit_price_rub is not None]
    if with_unit:
        best = min(with_unit, key=lambda o: o.unit_price_rub or o.price_rub)
        return best, None
    best = min(enriched, key=lambda o: o.price_rub)
    disclaimer = (
        "Сравнение по абсолютной цене упаковки — объём/вес в названии не распознан."
    )
    return best, disclaimer
