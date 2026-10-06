from __future__ import annotations

from egrocery.config import COVERAGE_NOTE
from egrocery.delivery_point import DeliveryPoint
from egrocery.loaders import SERVICE_DISPLAY, active_service_columns
from egrocery.models import Basket, BasketItem, Location
from egrocery.offers import Offer

PLACEHOLDER = "—"


def _row_label(item: BasketItem) -> str:
    if item.unit_hint:
        return f"{item.label} ({item.unit_hint})"
    return item.label


def _point_as_location(point: DeliveryPoint | Location) -> Location:
    if isinstance(point, DeliveryPoint):
        return Location(
            city=point.city,
            region=point.region,
            country=point.country,
            services_enabled=point.services_enabled,
            services_deferred=point.services_deferred,
            address_note=point.address_note,
            metro=point.metro,
        )
    return point


def format_basket_table(
    location: Location | DeliveryPoint,
    basket: Basket,
    *,
    cell_value: str = PLACEHOLDER,
    prices_by_service: dict[str, dict[str, str]] | None = None,
) -> str:
    loc = _point_as_location(location)
    services = active_service_columns(loc)
    headers = ["Позиция", *[SERVICE_DISPLAY[s] for s in services]]

    def escape_cell(text: str) -> str:
        return text.replace("|", "\\|")

    lines: list[str] = []
    title = f"Корзина **{basket.name}** — {loc.city}, {loc.region}"
    lines.append(title)
    if isinstance(location, DeliveryPoint):
        lines.append(f"_Точка доставки: {location.geo_summary()}_")
        if location.chat_id is not None:
            lines.append(f"_chat_id: {location.chat_id}_")
        if location.geocode_warning:
            lines.append(f"_{location.geocode_warning}_")
    lines.append("")
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for item in basket.items:
        cells: list[str] = []
        for service in services:
            if prices_by_service and service in prices_by_service:
                cells.append(prices_by_service[service].get(item.id, cell_value))
            else:
                cells.append(cell_value)
        row = [_row_label(item), *cells]
        lines.append("| " + " | ".join(escape_cell(c) for c in row) + " |")
    lines.append("")
    has_live = False
    if prices_by_service:
        for row in prices_by_service.values():
            if any(v != PLACEHOLDER for v in row.values()):
                has_live = True
                break
    if has_live:
        lines.append(f"_Цены — оценка по поиску витрины; {COVERAGE_NOTE}_")
    else:
        lines.append(f"_Цены недоступны или сервис вернул ошибку. {COVERAGE_NOTE}_")
    if loc.services_deferred:
        deferred = ", ".join(loc.services_deferred)
        lines.append(f"_Отложено: {deferred}._")
    return "\n".join(lines)


def format_search_table(
    point: DeliveryPoint,
    query: str,
    rows: list[tuple[str, Offer | None, str | None]],
    *,
    cheapest_service: str | None = None,
    errors: list[str] | None = None,
    disclaimer: str | None = None,
) -> str:
    headers = ["Сервис", "Товар", "Цена", "Ссылка"]

    def escape_cell(text: str) -> str:
        return text.replace("|", "\\|")

    lines: list[str] = [
        f"Поиск: **{query.strip()}**",
        f"_Точка: {point.geo_summary()}_",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for service, offer, link in rows:
        display = SERVICE_DISPLAY.get(service, service)
        if offer is None:
            row = [display, "—", "—", "—"]
        else:
            name = offer.product_name
            if offer is not None and service == cheapest_service:
                name = f"**{name}**"
            price = offer.display_price()
            if service == cheapest_service:
                price = f"**{price}**"
            link_cell = link or "—"
            row = [display, name, price, link_cell]
        lines.append("| " + " | ".join(escape_cell(c) for c in row) + " |")

    lines.append("")
    if cheapest_service:
        lines.append(
            f"_Минимальная цена: {SERVICE_DISPLAY.get(cheapest_service, cheapest_service)}._"
        )
    if disclaimer:
        lines.append(f"_{disclaimer}_")
    if errors:
        uniq = list(dict.fromkeys(errors))
        lines.append("_Ошибки провайдеров:_")
        for err in uniq[:5]:
            lines.append(f"- {err}")
    return "\n".join(lines)
