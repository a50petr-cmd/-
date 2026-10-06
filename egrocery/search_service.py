from __future__ import annotations

from pathlib import Path

from egrocery.config import get_location_path, get_store_root
from egrocery.delivery_point import ensure_delivery_point_geocoded, resolve_delivery_point
from egrocery.offers import Offer, pick_cheapest_offer
from egrocery.providers import search_all_providers
from egrocery.table import format_search_table


def build_search_markdown(
    query: str,
    *,
    chat_id: int | None = None,
    lat: float | None = None,
    lon: float | None = None,
    location_path: Path | None = None,
) -> str:
    loc_path = location_path or get_location_path()
    store = get_store_root()
    point = resolve_delivery_point(
        loc_path,
        chat_id=chat_id,
        store_root=store,
        lat=lat,
        lon=lon,
    )
    if chat_id is not None and lat is None and lon is None:
        point = ensure_delivery_point_geocoded(store, chat_id, point, loc_path)
    if chat_id is not None and not point.has_coordinates() and lat is None:
        return (
            "Нужна точка доставки: `/address` (текст или 📍), затем повторите поиск."
        )

    by_service = search_all_providers(point, query, limit=12)
    rows: list[tuple[str, Offer | None, str | None]] = []
    errors: list[str] = []
    for service, (offers, err) in by_service.items():
        if err:
            errors.append(err)
        best, _ = pick_cheapest_offer(offers)
        link = best.url if best else None
        rows.append((service, best, link))

    cheapest_service: str | None = None
    priced = [(s, o) for s, o, _ in rows if o is not None]
    if priced:
        best_pair = min(priced, key=lambda pair: pair[1].unit_price_rub or pair[1].price_rub)
        cheapest_service = best_pair[0]

    disclaimer: str | None = None
    if len(priced) > 1:
        _, disclaimer = pick_cheapest_offer([o for _, o in priced])

    return format_search_table(
        point,
        query,
        rows,
        cheapest_service=cheapest_service,
        errors=errors,
        disclaimer=disclaimer,
    )
