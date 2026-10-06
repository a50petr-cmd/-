from __future__ import annotations

from pathlib import Path

from egrocery.config import get_basket_path, get_location_path, get_store_root
from egrocery.delivery_point import resolve_delivery_point
from egrocery.loaders import load_basket
from egrocery.providers import fetch_all_provider_prices
from egrocery.table import format_basket_table


def build_basket_markdown(
    *,
    location_path: Path | None = None,
    basket_path: Path | None = None,
    chat_id: int | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> str:
    loc_path = location_path or get_location_path()
    basket_p = basket_path or get_basket_path()
    store = get_store_root()
    point = resolve_delivery_point(
        loc_path,
        chat_id=chat_id,
        store_root=store,
        lat=lat,
        lon=lon,
    )
    basket = load_basket(basket_p)
    prices_by_service = fetch_all_provider_prices(point, basket)
    return format_basket_table(point, basket, prices_by_service=prices_by_service)
