from datetime import date
from decimal import Decimal

from kopilka.format import format_digest
from kopilka.recurring import RecurringHit, TransactionView, detect_recurring


def _tx(label: str, amount: str, day: date, url: str | None = None) -> TransactionView:
    return TransactionView(amount=Decimal(amount), label=label, occurred_on=day, cancel_url=url)


def test_monthly_same_label_is_a_subscription():
    hits = detect_recurring([
        _tx("Кинопоиск", "299", date(2026, 8, 1)),
        _tx("кинопоиск", "299.00", date(2026, 9, 1)),
        _tx("Подписка Кинопоиск", "299", date(2026, 10, 1), "https://example.com/off"),
    ])
    assert hits == [
        RecurringHit(
            label="Подписка Кинопоиск",
            amount=Decimal("299.00"),
            count=3,
            last_on=date(2026, 10, 1),
            cancel_url="https://example.com/off",
        )
    ]


def test_short_gap_and_single_charge_are_ignored():
    assert detect_recurring([
        _tx("Кофе", "180", date(2026, 10, 1)),
        _tx("Кофе", "180", date(2026, 10, 6)),
    ]) == []
    assert detect_recurring([_tx("Кинопоиск", "299", date(2026, 10, 1))]) == []


def test_edges_of_the_month_window():
    assert detect_recurring([
        _tx("Фитнес", "2500", date(2026, 9, 1)),
        _tx("Фитнес", "2500", date(2026, 9, 26)),
    ])
    assert detect_recurring([
        _tx("Фитнес", "2500", date(2026, 9, 1)),
        _tx("Фитнес", "2500", date(2026, 10, 6)),
    ])
    assert not detect_recurring([
        _tx("Фитнес", "2500", date(2026, 9, 1)),
        _tx("Фитнес", "2500", date(2026, 9, 25)),
    ])
    assert not detect_recurring([
        _tx("Фитнес", "2500", date(2026, 9, 1)),
        _tx("Фитнес", "2500", date(2026, 10, 7)),
    ])


def test_loose_window_needs_three_charges():
    hits = detect_recurring([
        _tx("Курсы", "1500", date(2026, 1, 1)),
        _tx("Курсы", "1500", date(2026, 1, 23)),
        _tx("Курсы", "1500", date(2026, 2, 22)),
        _tx("Курсы", "1500", date(2026, 3, 27)),
    ])
    assert len(hits) == 1
    assert hits[0].count == 4


def test_different_labels_or_amounts_stay_apart():
    hits = detect_recurring([
        _tx("Кинопоиск", "299", date(2026, 8, 1)),
        _tx("Фитнес", "299", date(2026, 9, 1)),
        _tx("Кинопоиск", "399", date(2026, 10, 1)),
    ])
    assert hits == []


def test_digest_prints_only_a_stored_link():
    with_link = RecurringHit("Кинопоиск", Decimal("299.00"), 2, date(2026, 10, 1), "https://example.com/off")
    without = RecurringHit("Фитнес", Decimal("2500.00"), 2, date(2026, 10, 3), None)
    text = format_digest([with_link, without])
    assert "https://example.com/off" in text
    assert "Ссылку на отписку ты не оставлял." in text
    fitness_line = next(line for line in text.splitlines() if line.startswith("• Фитнес"))
    assert "http" not in fitness_line


def test_empty_digest_has_no_link():
    text = format_digest([])
    assert "http" not in text
    assert "не вижу" in text
