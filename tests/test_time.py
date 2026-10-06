from datetime import datetime

from kopilka.timeutil import parse_timezone, start_of_week_utc_naive


def test_moscow_week_boundary_in_utc():
    sunday_evening = datetime(2026, 10, 4, 20, 0)
    monday_night = datetime(2026, 10, 4, 22, 0)
    assert start_of_week_utc_naive(sunday_evening, "Europe/Moscow") == datetime(2026, 9, 27, 21, 0)
    assert start_of_week_utc_naive(monday_night, "Europe/Moscow") == datetime(2026, 10, 4, 21, 0)


def test_default_timezone_aliases():
    assert parse_timezone("ок") == "Europe/Moscow"
    assert parse_timezone("Москва") == "Europe/Moscow"
    assert parse_timezone("Asia/Yekaterinburg") == "Asia/Yekaterinburg"
    assert parse_timezone("Несуществующий/Город") is None
