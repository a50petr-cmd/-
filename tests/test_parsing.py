from decimal import Decimal

from kopilka.parsing import looks_like_impulse, parse_money, parse_user_text
from kopilka.parsing import ParsedExpense, ParsedImpulse


def test_burger_phrase_sets_category_and_amount():
    parsed = parse_user_text("купил бургер за 450")
    assert isinstance(parsed, ParsedExpense)
    assert parsed.title == "бургер"
    assert parsed.amount == Decimal("450.00")
    assert parsed.category == "фастфуд"


def test_burger_accepts_currency_words_and_quotes():
    for phrase in ("Купил бургер за 450р", "купил бургер за 450 рублей", "«купил бургер за 450»"):
        parsed = parse_user_text(phrase)
        assert isinstance(parsed, ParsedExpense)
        assert parsed.amount == Decimal("450.00")
        assert parsed.category == "фастфуд"


def test_spent_on_taxi():
    parsed = parse_user_text("потратил 500 на такси")
    assert isinstance(parsed, ParsedExpense)
    assert parsed.title == "такси"
    assert parsed.amount == Decimal("500.00")
    assert parsed.category == "такси"


def test_amount_with_spaces_and_coffee():
    parsed = parse_user_text("Потратила 1 200 на продукты")
    assert isinstance(parsed, ParsedExpense)
    assert parsed.amount == Decimal("1200.00")
    assert parsed.category == "продукты"

    coffee = parse_user_text("кофе за 180")
    assert isinstance(coffee, ParsedExpense)
    assert coffee.amount == Decimal("180.00")
    assert coffee.category == "кафе"


def test_subscription_word_is_not_cinema():
    parsed = parse_user_text("оплатил кинопоиск за 299")
    assert isinstance(parsed, ParsedExpense)
    assert parsed.category == "подписки"
    assert parsed.amount == Decimal("299.00")


def test_impulse_thousands_and_spaced_price():
    ps5 = parse_user_text("хочу купить PS5 за 60к")
    assert isinstance(ps5, ParsedImpulse)
    assert ps5.title == "PS5"
    assert ps5.price == Decimal("60000.00")

    phone = parse_user_text("Хочу купить новый iPhone за 120 000")
    assert isinstance(phone, ParsedImpulse)
    assert phone.title == "новый iPhone"
    assert phone.price == Decimal("120000.00")

    course = parse_user_text("хочу купить курс за 1,5к")
    assert isinstance(course, ParsedImpulse)
    assert course.price == Decimal("1500.00")


def test_unparsed_text_and_impulse_without_price():
    assert parse_user_text("привет") is None
    assert parse_user_text("хочу купить PS5") is None
    assert looks_like_impulse("хочу купить PS5")
    assert not looks_like_impulse("купил бургер за 450")


def test_salary_amounts():
    assert parse_money("120000") == Decimal("120000.00")
    assert parse_money("120 000") == Decimal("120000.00")
    assert parse_money("120к") == Decimal("120000.00")
    assert parse_money("ок") is None
    assert parse_money("0") is None
