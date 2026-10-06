"""Повтор одной и той же суммы примерно раз в месяц. Только по уже записанным тратам."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

_STOP_WORDS = frozenset({"подписка", "оплата", "списание", "платеж", "сервис", "за"})


@dataclass(frozen=True)
class TransactionView:
    amount: Decimal
    label: str
    occurred_on: date
    cancel_url: str | None = None


@dataclass(frozen=True)
class RecurringHit:
    label: str
    amount: Decimal
    count: int
    last_on: date
    cancel_url: str | None


def norm_label(label: str) -> str:
    folded = label.lower().replace("ё", "е")
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in folded)
    parts = [part for part in cleaned.split() if part not in _STOP_WORDS]
    return " ".join(parts) or " ".join(cleaned.split())


def _is_monthly(gaps: list[int]) -> bool:
    if not gaps:
        return False
    if all(25 <= gap <= 35 for gap in gaps):
        return True
    if len(gaps) >= 2 and all(20 <= gap <= 40 for gap in gaps):
        ordered = sorted(gaps)
        median = ordered[len(ordered) // 2]
        return 25 <= median <= 35
    return False


def detect_recurring(transactions: list[TransactionView]) -> list[RecurringHit]:
    groups: dict[tuple[str, Decimal], list[TransactionView]] = {}
    for tx in transactions:
        key = (norm_label(tx.label), Decimal(tx.amount).quantize(Decimal("0.01")))
        if not key[0]:
            continue
        groups.setdefault(key, []).append(tx)

    hits: list[RecurringHit] = []
    for items in groups.values():
        ordered = sorted(items, key=lambda item: (item.occurred_on, item.label))
        if len(ordered) < 2:
            continue
        gaps = [
            (later.occurred_on - earlier.occurred_on).days
            for earlier, later in zip(ordered, ordered[1:])
        ]
        if not _is_monthly(gaps):
            continue
        url = next((item.cancel_url for item in reversed(ordered) if item.cancel_url), None)
        last = ordered[-1]
        hits.append(
            RecurringHit(
                label=last.label,
                amount=Decimal(last.amount).quantize(Decimal("0.01")),
                count=len(ordered),
                last_on=last.occurred_on,
                cancel_url=url,
            )
        )
    hits.sort(key=lambda hit: (-hit.amount, hit.label))
    return hits
