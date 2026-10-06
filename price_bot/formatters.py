from __future__ import annotations

from price_bot.models import ComparisonResult, ProductListing


def _price_str(price: int | None) -> str:
    if price is None:
        return "цена неизвестна"
    return f"{price:,}".replace(",", " ") + " ₽"


def format_comparison_message(result: ComparisonResult) -> str:
    lines: list[str] = []
    lines.append("🛒 Сравнение цен (Ozon / WB / Яндекс Маркет)")
    lines.append("")
    lines.append(f"Исходный товар ({result.source.platform.label_ru}):")
    lines.append(result.source.title[:200])
    lines.append(f"Цена: {_price_str(result.source.price_rub)}")
    lines.append(result.source.url)
    lines.append("")

    all_items = result.all_listings()
    priced = [x for x in all_items if x.price_rub is not None]
    priced.sort(key=lambda x: x.price_rub or 0)

    lines.append("Предложения (от дешёвого):")
    if not priced:
        lines.append("— не удалось получить цены для сравнения")
    else:
        cheapest = min(priced, key=lambda x: x.price_rub or 0)
        for item in priced:
            marker = "✅ " if item is cheapest else "• "
            label = getattr(item, "match_label", "исходная ссылка" if item.is_source else "")
            score = getattr(item, "match_score", None)
            extra = ""
            if score is not None and not item.is_source:
                extra = f" ({label}, {int(score * 100)}%)"
            elif label:
                extra = f" ({label})"
            lines.append(
                f"{marker}{item.platform.label_ru}: {_price_str(item.price_rub)}{extra}"
            )
            lines.append(f"  {item.url}")

    lines.append("")
    lines.append(
        "⚠️ Сопоставление эвристическое: проверяйте модель и комплектацию. "
        "Цены публичные, без персональных скидок и Ozon Premium/WB-кошелька."
    )
    if result.errors:
        lines.append("")
        lines.append("Заметки:")
        for err in result.errors[:5]:
            lines.append(f"• {err}")
    return "\n".join(lines)


def format_listing_short(item: ProductListing) -> str:
    return f"{item.platform.label_ru}: {_price_str(item.price_rub)} — {item.url}"
