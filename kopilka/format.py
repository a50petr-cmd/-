from decimal import Decimal

from kopilka.recurring import RecurringHit


def format_rub(amount: Decimal) -> str:
    value = Decimal(amount).quantize(Decimal("0.01"))
    sign = "-" if value < 0 else ""
    value = abs(value)
    whole = int(value)
    frac = int((value - Decimal(whole)) * 100)
    body = f"{whole:,}".replace(",", " ")
    if frac:
        return f"{sign}{body},{frac:02d} ₽"
    return f"{sign}{body} ₽"


def format_percent(value: Decimal) -> str:
    quantized = Decimal(value).quantize(Decimal("0.01"))
    text = f"{quantized:.2f}"
    if text.endswith(".00"):
        return str(int(quantized))
    return text.rstrip("0").replace(".", ",")


def format_hours(hours: Decimal) -> str:
    quantized = Decimal(hours).quantize(Decimal("0.1"))
    text = f"{quantized:.1f}"
    if text.endswith(".0"):
        return str(int(quantized))
    return text.replace(".", ",")


def format_digest(hits: list[RecurringHit]) -> str:
    if not hits:
        return (
            "Повторяющихся списаний пока не вижу. "
            "Нужны одно и то же название и сумма хотя бы два раза, с паузой около месяца."
        )
    lines = [
        "Похоже на подписки. Смотрю только то, что ты уже записал, банк не открываю.",
        "",
    ]
    for hit in hits:
        when = hit.last_on.strftime("%d.%m.%Y")
        line = f"• {hit.label} — {format_rub(hit.amount)}, {hit.count} раз, последнее {when}."
        if hit.cancel_url:
            line += f" Отписка: {hit.cancel_url}"
        else:
            line += " Ссылку на отписку ты не оставлял."
        lines.append(line)
    lines.append("")
    lines.append("Если сервисом не пользовался — отмени. Обычно так выходит несколько сотен или пара тысяч в месяц.")
    return "\n".join(lines)
