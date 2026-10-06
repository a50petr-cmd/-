from decimal import Decimal

from kopilka.utility import interpret


def test_russian_budget_and_challenge_phrases():
    budget = interpret("бюджет 7 000")
    assert budget is not None
    assert budget.kind == "budget_set"
    assert budget.number == Decimal("7000.00")

    challenge = interpret("неделя без такси")
    assert challenge is not None
    assert challenge.kind == "challenge_start"
    assert challenge.text == "такси"

    assert interpret("купил бургер за 450") is None


def test_cashback_unsub_and_slash_command():
    cashback = interpret("кэшбэк Зарплатная карта продукты 5")
    assert cashback is not None
    assert cashback.kind == "cashback"
    assert cashback.text == "Зарплатная карта"
    assert cashback.extra == "продукты"
    assert cashback.number == Decimal("5.00")

    link = interpret("отписка Кинопоиск https://example.com/off")
    assert link is not None
    assert link.kind == "unsub"
    assert link.text == "Кинопоиск"
    assert link.url == "https://example.com/off"

    slash = interpret("/challenge@KopilkaBot такси")
    assert slash is not None
    assert slash.kind == "challenge_start"
    assert slash.text == "такси"
