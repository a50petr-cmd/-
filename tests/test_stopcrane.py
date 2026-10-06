from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from kopilka.money import confirmation_allowed, exceeds_salary_share, hours_of_work
from kopilka.render import threshold_clause


def test_threshold_is_strictly_above_ten_percent():
    salary = Decimal("100000")
    assert exceeds_salary_share(Decimal("10000"), salary) is False
    assert exceeds_salary_share(Decimal("9999"), salary) is False
    assert exceeds_salary_share(Decimal("10000.01"), salary) is True
    assert exceeds_salary_share(Decimal("60000"), salary) is True


def test_threshold_rejects_bad_salary():
    with pytest.raises(ValueError):
        exceeds_salary_share(Decimal("100"), Decimal("0"))
    with pytest.raises(ValueError):
        exceeds_salary_share(Decimal("-1"), Decimal("100000"))


def test_hours_of_work_from_monthly_salary():
    assert hours_of_work(Decimal("60000"), Decimal("100000"), 160) == Decimal("96.0")
    assert hours_of_work(Decimal("4500"), Decimal("160000"), 160) == Decimal("4.5")


def test_confirmation_waits_full_day():
    started = datetime(2026, 10, 6, 12, 0, 0)
    assert confirmation_allowed(started, started + timedelta(hours=24))
    assert not confirmation_allowed(started, started + timedelta(hours=24) - timedelta(seconds=1))


def test_confirmation_compares_time_zones():
    requested = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    moscow_next_day = datetime(2026, 10, 7, 15, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    assert confirmation_allowed(requested, moscow_next_day)
    one_minute_earlier = moscow_next_day - timedelta(minutes=1)
    assert not confirmation_allowed(requested, one_minute_earlier)


def test_threshold_wording_matches_the_boundary():
    salary = Decimal("100000")
    exact = threshold_clause(Decimal("10000"), salary)
    assert "Порог не пробит" in exact
    assert "порог 10% пробит" not in exact

    just_over = threshold_clause(Decimal("10000.01"), salary)
    assert "больше 10%" in just_over

    big = threshold_clause(Decimal("60000"), salary)
    assert "порог 10% пробит" in big
