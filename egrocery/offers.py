from __future__ import annotations

import re
from dataclasses import dataclass

_GRAMS_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(кг|г|g)\b", re.IGNORECASE
)
_LITERS_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(л|l|мл|ml)\b", re.IGNORECASE
)
_FAT_QUERY_RE = re.compile(r"(\d+[.,]\d+|\d+)\s*%")
_FAT_NAME_RE = re.compile(r"(\d+[.,]\d+|\d+)\s*%")


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


def _parse_fat_percent(text: str) -> float | None:
    m = _FAT_NAME_RE.search(text.replace(" ", ""))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def target_fat_from_query(query: str) -> float | None:
    m = _FAT_QUERY_RE.search(query.replace(" ", ""))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _normalize_ru(text: str) -> str:
    return text.lower().replace("ё", "е")


def _query_keywords(query: str) -> list[str]:
    q = _normalize_ru(_FAT_QUERY_RE.sub(" ", query))
    words = re.findall(r"[a-zа-я0-9]+", q, re.IGNORECASE)
    keywords: list[str] = []
    for w in words:
        w = _normalize_ru(w)
        if len(w) < 3 or w.isdigit():
            continue
        keywords.append(w)
    return keywords


def _name_matches_keywords(name: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    n = _normalize_ru(name)
    for kw in keywords:
        if kw in n:
            continue
        stem = kw[: max(4, len(kw) - 1)]
        if stem and stem in n:
            continue
        return False
    return True


def _filter_by_fat(
    offers: list[Offer], target: float
) -> tuple[list[Offer], str | None]:
    exact: list[Offer] = []
    close: list[Offer] = []
    for offer in offers:
        fat = _parse_fat_percent(offer.product_name)
        if fat is None:
            continue
        if abs(fat - target) < 0.05:
            exact.append(offer)
        elif abs(fat - target) <= 0.6:
            close.append(offer)
    if exact:
        return exact, None
    if close:
        return close, f"Нет ровно {target:g}% — показаны близкие по жирности."
    return offers, f"Нет совпадения по {target:g}% — показан самый дешёвый из выдачи."


def filter_offers_for_query(offers: list[Offer], query: str) -> tuple[list[Offer], str | None]:
    """Match query keywords (сметана, молоко…) and optional fat %%."""
    if not offers:
        return offers, None
    notes: list[str] = []
    keywords = _query_keywords(query)
    pool = offers
    if keywords:
        matched = [o for o in offers if _name_matches_keywords(o.product_name, keywords)]
        if matched:
            pool = matched
        else:
            notes.append(
                f"Нет товара с «{' '.join(keywords)}» в названии — показана вся выдача."
            )
    target = target_fat_from_query(query)
    if target is not None:
        pool, fat_note = _filter_by_fat(pool, target)
        if fat_note:
            notes.append(fat_note)
    note = " ".join(notes) if notes else None
    return pool, note


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
