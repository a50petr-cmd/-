"""Разбор коротких фраз. Не модель: шаблоны на то, как люди пишут в чат."""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from kopilka.categories import categorize

_VERBS = (
    "потратила",
    "потратили",
    "потратил",
    "заплатила",
    "заплатили",
    "заплатил",
    "оплатила",
    "оплатили",
    "оплатил",
    "списала",
    "списали",
    "списал",
    "купила",
    "купили",
    "купил",
    "взяла",
    "взяли",
    "взял",
)
_VERB = "(?:" + "|".join(_VERBS) + ")"
_NUMBER = r"\d[\d\s]*(?:[.,]\d+)?"
_SUFFIX = r"(?:тысяч[аи]?|тыс\.?|к|k)"
_CURRENCY = r"(?:рублей|рубля|рубль|руб\.?|₽|р\.?)"
_AMOUNT = rf"(?P<amount>{_NUMBER})\s*(?P<suffix>{_SUFFIX})?\s*(?:{_CURRENCY})?"

_IMPULSE = re.compile(
    rf"^\s*хочу\s+(?:купить|взять)\s+(?P<title>.+?)\s+за\s+{_AMOUNT}\s*$",
    re.IGNORECASE,
)
_EXPENSE_TITLE_FIRST = re.compile(
    rf"^\s*{_VERB}\s+(?P<title>.+?)\s+за\s+{_AMOUNT}\s*$",
    re.IGNORECASE,
)
_EXPENSE_AMOUNT_FIRST = re.compile(
    rf"^\s*{_VERB}\s+{_AMOUNT}\s+(?:на|за)\s+(?P<title>.+?)\s*$",
    re.IGNORECASE,
)
_BARE_TITLE = re.compile(
    rf"^\s*(?P<title>.+?)\s+за\s+{_AMOUNT}\s*$",
    re.IGNORECASE,
)
_MONEY = re.compile(
    rf"^\s*(?P<amount>{_NUMBER})\s*(?P<suffix>{_SUFFIX})?\s*(?:{_CURRENCY})?\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedExpense:
    title: str
    amount: Decimal
    category: str


@dataclass(frozen=True)
class ParsedImpulse:
    title: str
    price: Decimal


def normalize_text(text: str) -> str:
    cleaned = text.strip()
    if len(cleaned) >= 2 and cleaned[0] in "\"'«“" and cleaned[-1] in "\"'»”":
        cleaned = cleaned[1:-1].strip()
    return cleaned.rstrip(".!?")


def parse_amount(number: str, suffix: str | None) -> Decimal | None:
    cleaned = number.replace(" ", "").replace(",", ".")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    if suffix:
        value *= 1000
    if value <= 0 or value >= Decimal("1000000000"):
        return None
    return value.quantize(Decimal("0.01"))


def parse_money(text: str) -> Decimal | None:
    match = _MONEY.fullmatch(text.strip())
    if not match:
        return None
    return parse_amount(match.group("amount"), match.group("suffix"))


def _clean_title(title: str) -> str:
    return " ".join(title.strip().strip("\"'«»“”.,!?").split())


def _from_match(match: re.Match[str], *, impulse: bool) -> ParsedExpense | ParsedImpulse | None:
    title = _clean_title(match.group("title"))
    amount = parse_amount(match.group("amount"), match.group("suffix"))
    if not title or amount is None:
        return None
    if impulse:
        return ParsedImpulse(title=title, price=amount)
    return ParsedExpense(title=title, amount=amount, category=categorize(title))


def looks_like_impulse(text: str) -> bool:
    folded = normalize_text(text).lower().replace("ё", "е")
    return folded.startswith("хочу купить") or folded.startswith("хочу взять")


def parse_decision(text: str) -> str | None:
    folded = normalize_text(text).lower().replace("ё", "е")
    if folded in {"да", "yes"}:
        return "yes"
    if folded in {"нет", "no"}:
        return "no"
    return None


def parse_user_text(text: str) -> ParsedExpense | ParsedImpulse | None:
    normalized = normalize_text(text)
    if not normalized:
        return None
    impulse = _IMPULSE.fullmatch(normalized)
    if impulse:
        return _from_match(impulse, impulse=True)
    for pattern in (_EXPENSE_TITLE_FIRST, _EXPENSE_AMOUNT_FIRST, _BARE_TITLE):
        match = pattern.fullmatch(normalized)
        if match:
            return _from_match(match, impulse=False)
    return None
