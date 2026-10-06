"""Короткие команды. Траты и «хочу купить» разбирает parsing.py."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from kopilka.parsing import parse_money


@dataclass(frozen=True)
class Utility:
    kind: str
    text: str = ""
    extra: str = ""
    number: Decimal | None = None
    url: str = ""


def interpret(text: str) -> Utility | None:
    raw = " ".join(text.strip().split())
    if not raw:
        return None
    if raw.startswith("/"):
        head, _, rest = raw.partition(" ")
        name = head[1:].split("@", 1)[0].lower()
        return _slash(name, rest.strip())
    return _phrase(raw)


def _slash(name: str, rest: str) -> Utility:
    if name == "help":
        return Utility("help")
    if name == "week":
        return Utility("week")
    if name == "piggy":
        return Utility("piggy")
    if name == "expenses":
        return Utility("expenses")
    if name == "digest":
        return Utility("digest")
    if name in {"subs", "subscriptions"}:
        return Utility("subs")
    if name == "cards":
        return Utility("cards")
    if name in {"categories", "cats"}:
        return Utility("categories")
    if name == "challenge":
        if not rest:
            return Utility("challenge_status")
        return Utility("challenge_start", text=rest)
    if name == "salary":
        return _money_command("salary", rest)
    if name == "budget":
        if not rest:
            return Utility("week")
        return _money_command("budget", rest)
    if name == "card":
        if not rest:
            return Utility("card_bad")
        return Utility("card_add", text=rest)
    if name == "cashback":
        return _cashback(rest)
    if name == "hint":
        if not rest:
            return Utility("hint_bad")
        return Utility("hint", text=rest)
    if name == "unsub":
        return _unsub(rest)
    if name == "tz":
        if not rest:
            return Utility("tz_bad")
        return Utility("tz_set", text=rest)
    return Utility("unknown")


def _money_command(which: str, rest: str) -> Utility:
    if not rest:
        return Utility("salary_show" if which == "salary" else "week")
    number = parse_money(rest)
    if number is None:
        return Utility("salary_bad" if which == "salary" else "budget_bad")
    kind = "salary_set" if which == "salary" else "budget_set"
    return Utility(kind, number=number)


def _cashback(rest: str) -> Utility:
    parts = rest.split()
    if len(parts) < 3:
        return Utility("cashback_bad")
    token = parts[-1].replace(",", ".")
    try:
        percent = Decimal(token)
    except InvalidOperation:
        return Utility("cashback_bad")
    if percent < 0 or percent > 100:
        return Utility("cashback_bad")
    card = " ".join(parts[:-2]).strip()
    if not card:
        return Utility("cashback_bad")
    return Utility("cashback", text=card, extra=parts[-2], number=percent.quantize(Decimal("0.01")))


def _unsub(rest: str) -> Utility:
    parts = rest.split()
    if len(parts) < 2 or not parts[-1].lower().startswith(("http://", "https://")):
        return Utility("unsub_bad")
    label = " ".join(parts[:-1]).strip()
    if not label:
        return Utility("unsub_bad")
    return Utility("unsub", text=label, url=parts[-1])


def _phrase(raw: str) -> Utility | None:
    folded = raw.lower().replace("ё", "е")
    if folded in {"помощь", "команды"}:
        return Utility("help")
    if folded == "копилка":
        return Utility("piggy")
    if folded in {"траты", "история"}:
        return Utility("expenses")
    if folded == "подписки":
        return Utility("subs")
    if folded == "дайджест":
        return Utility("digest")
    if folded == "карты":
        return Utility("cards")
    if folded == "категории":
        return Utility("categories")
    if folded == "челлендж":
        return Utility("challenge_status")
    if folded.startswith("челлендж "):
        payload = raw.split(maxsplit=1)[1].strip()
        return Utility("challenge_start", text=payload) if payload else Utility("challenge_bad")
    if folded.startswith("неделя без"):
        parts = raw.split(maxsplit=2)
        if len(parts) < 3 or not parts[2].strip():
            return Utility("challenge_bad")
        return Utility("challenge_start", text=parts[2].strip())
    if folded in {"неделя", "бюджет"}:
        return Utility("week")
    if folded.startswith("неделя ") or folded.startswith("бюджет "):
        number = parse_money(raw.split(maxsplit=1)[1])
        if number is None:
            return Utility("budget_bad")
        return Utility("budget_set", number=number)
    if folded == "зарплата":
        return Utility("salary_show")
    if folded.startswith("зарплата "):
        number = parse_money(raw.split(maxsplit=1)[1])
        if number is None:
            return Utility("salary_bad")
        return Utility("salary_set", number=number)
    if folded.startswith("карта "):
        name = raw.split(maxsplit=1)[1].strip()
        return Utility("card_add", text=name) if name else Utility("card_bad")
    if folded.startswith(("кэшбэк ", "кэшбек ", "кешбек ")):
        return _cashback(raw.split(maxsplit=1)[1])
    if folded in {"подсказка", "какой картой"}:
        return Utility("hint_bad")
    if folded.startswith("подсказка "):
        payload = raw.split(maxsplit=1)[1].strip()
        return Utility("hint", text=payload) if payload else Utility("hint_bad")
    if folded.startswith("какой картой "):
        parts = raw.split(maxsplit=2)
        if len(parts) < 3 or not parts[2].strip():
            return Utility("hint_bad")
        return Utility("hint", text=parts[2].strip())
    if folded.startswith("отписка "):
        return _unsub(raw.split(maxsplit=1)[1])
    if folded.startswith("пояс "):
        payload = raw.split(maxsplit=1)[1].strip()
        return Utility("tz_set", text=payload) if payload else Utility("tz_bad")
    if folded.startswith("часовой пояс "):
        parts = raw.split(maxsplit=2)
        if len(parts) < 3 or not parts[2].strip():
            return Utility("tz_bad")
        return Utility("tz_set", text=parts[2].strip())
    return None
