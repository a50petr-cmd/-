from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from kopilka.db import init_db
from kopilka.recurring import detect_recurring
from kopilka.repo import (
    add_card,
    add_expense,
    best_cashback,
    create_user,
    decide_impulse,
    last_declined,
    load_transactions,
    open_impulse,
    set_cashback,
    start_challenge,
    active_challenge,
)


@pytest.fixture()
def database():
    init_db("sqlite://")


def _user(database):
    return create_user(1, Decimal("100000"), Decimal("2000"), "Europe/Moscow")


def test_week_budget_ignores_previous_week_and_keeps_roundup(database):
    user = _user(database)
    this_week = datetime(2026, 10, 7, 12, 0)
    previous_week = datetime(2026, 9, 30, 12, 0)

    add_expense(
        user.id,
        title="бургер",
        amount=Decimal("450"),
        category="фастфуд",
        raw_text="старое",
        now=previous_week,
    )
    first = add_expense(
        user.id,
        title="бургер",
        amount=Decimal("450"),
        category="фастфуд",
        raw_text="купил бургер за 450",
        now=this_week,
    )
    assert first.piggy_delta == Decimal("50.00")
    assert first.week_count == 1
    assert first.budget_left == Decimal("1550.00")
    assert first.piggy_total == Decimal("100.00")

    other = add_expense(
        user.id,
        title="метро",
        amount=Decimal("100"),
        category="транспорт",
        raw_text="метро за 100",
        now=this_week + timedelta(hours=1),
    )
    assert other.piggy_delta == Decimal("0.00")
    assert other.week_count == 1
    assert other.budget_left == Decimal("1450.00")
    assert other.piggy_total == Decimal("100.00")

    second = add_expense(
        user.id,
        title="бургер",
        amount=Decimal("450"),
        category="фастфуд",
        raw_text="ещё",
        now=this_week + timedelta(hours=2),
    )
    assert second.week_count == 2
    assert second.budget_left == Decimal("1000.00")
    assert second.piggy_total == Decimal("150.00")


def test_challenge_reset_and_completion(database):
    user = _user(database)
    start = datetime(2026, 10, 7, 12, 0)
    add_expense(
        user.id,
        title="яндекс go",
        amount=Decimal("500"),
        category="такси",
        raw_text="такси",
        now=start - timedelta(days=2),
    )
    started, replaced = start_challenge(user.id, "такси", now=start)
    assert replaced is None
    assert started.saved == Decimal("500.00")

    reset = add_expense(
        user.id,
        title="яндекс go",
        amount=Decimal("400"),
        category="такси",
        raw_text="снова такси",
        now=start + timedelta(hours=1),
    )
    assert reset.challenge_reset
    assert not reset.challenge_completed
    active = active_challenge(user.id)
    assert active is not None
    assert active.started_at == start + timedelta(hours=1)

    done = add_expense(
        user.id,
        title="кофе",
        amount=Decimal("180"),
        category="кафе",
        raw_text="кофе за 180",
        now=active.started_at + timedelta(days=7),
    )
    assert done.challenge_completed
    assert done.challenge_category == "такси"
    assert done.challenge_saved == Decimal("500.00")


def test_declined_impulse_is_remembered(database):
    user = _user(database)
    moment = datetime(2026, 10, 6, 12, 0)
    opened = open_impulse(user.id, "PS5", Decimal("60000"), now=moment)
    assert last_declined(user.id) is None
    decide_impulse(opened.id, "declined", now=moment)
    remembered = last_declined(user.id)
    assert remembered is not None
    assert remembered.title == "PS5"
    assert remembered.price == Decimal("60000.00")


def test_cashback_picks_the_highest_rate(database):
    user = _user(database)
    add_card(user.id, "Бета")
    add_card(user.id, "Альфа")
    assert set_cashback(user.id, "нет такой", "продукты", Decimal("9")) is False
    set_cashback(user.id, "бета", "продукты", Decimal("5"))
    set_cashback(user.id, "Альфа", "продукты", Decimal("5"))
    set_cashback(user.id, "Альфа", "кафе", Decimal("1"))
    name, percent = best_cashback(user.id, "продукты")
    assert name == "Альфа"
    assert percent == Decimal("5.00")


def test_stored_cancel_link_reaches_recurring_detection(database):
    user = _user(database)
    add_expense(
        user.id,
        title="Кинопоиск",
        amount=Decimal("299"),
        category="подписки",
        raw_text="кинопоиск",
        now=datetime(2026, 9, 1, 9, 0),
    )
    add_expense(
        user.id,
        title="кинопоиск",
        amount=Decimal("299"),
        category="подписки",
        raw_text="ещё",
        now=datetime(2026, 10, 1, 9, 0),
    )
    from kopilka.repo import save_cancel_link

    save_cancel_link(user.id, "Кинопоиск", "https://example.com/off")
    hits = detect_recurring(load_transactions(user.id))
    assert len(hits) == 1
    assert hits[0].count == 2
    assert hits[0].amount == Decimal("299.00")
    assert hits[0].cancel_url == "https://example.com/off"
