from datetime import datetime, timedelta

from kopilka.categories import breaks_challenge
from kopilka.money import challenge_finished


def test_challenge_breaks_on_category_or_title():
    assert breaks_challenge("такси", "такси", "метро")
    assert not breaks_challenge("такси", "кафе", "кофе")
    assert breaks_challenge("сладости", "прочее", "сладости у дома")
    assert not breaks_challenge("сладости", "прочее", "шоколад")


def test_challenge_lasts_seven_days():
    started = datetime(2026, 10, 1, 9, 0)
    assert not challenge_finished(started, started + timedelta(days=7) - timedelta(seconds=1))
    assert challenge_finished(started, started + timedelta(days=7))
