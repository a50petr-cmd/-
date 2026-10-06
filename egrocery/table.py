from __future__ import annotations

from egrocery.config import COVERAGE_NOTE
from egrocery.loaders import SERVICE_DISPLAY, active_service_columns
from egrocery.models import Basket, BasketItem, Location

PLACEHOLDER = "—"


def _row_label(item: BasketItem) -> str:
    if item.unit_hint:
        return f"{item.label} ({item.unit_hint})"
    return item.label


def format_basket_table(
    location: Location,
    basket: Basket,
    *,
    cell_value: str = PLACEHOLDER,
) -> str:
    services = active_service_columns(location)
    headers = ["Позиция", *[SERVICE_DISPLAY[s] for s in services]]

    def escape_cell(text: str) -> str:
        return text.replace("|", "\\|")

    lines: list[str] = []
    title = f"Корзина **{basket.name}** — {location.city}, {location.region}"
    lines.append(title)
    lines.append("")
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for item in basket.items:
        row = [_row_label(item), *[cell_value for _ in services]]
        lines.append("| " + " | ".join(escape_cell(c) for c in row) + " |")
    lines.append("")
    lines.append(f"_P0: цены вручную / TBD. {COVERAGE_NOTE}_")
    if location.services_deferred:
        deferred = ", ".join(location.services_deferred)
        lines.append(f"_Отложено: {deferred}._")
    return "\n".join(lines)
