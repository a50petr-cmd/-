"""Категории из слов в фразе. Список короткий и явный, без внешней модели."""

CATEGORY_ORDER = (
    "фастфуд",
    "кафе",
    "продукты",
    "такси",
    "доставка",
    "азс",
    "транспорт",
    "подписки",
    "фитнес",
    "связь",
    "здоровье",
    "одежда",
    "развлечения",
    "жилье",
    "прочее",
)

_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("фастфуд", ("бургер", "шаурм", "пицц", "донер", "макдак", "kfc", "ролл", "суши", "фастфуд")),
    ("такси", ("такси", "яндекс go", "uber", "ситимобил")),
    ("доставка", ("доставк", "delivery", "яндекс еда", "самокат")),
    ("кафе", ("кофе", "латте", "капучино", "кафе", "ресторан")),
    ("продукты", ("продукт", "пятероч", "магнит", "перекрест", "лента", "ашан", "молок", "хлеб")),
    ("азс", ("азс", "бензин", "заправк", "лукойл")),
    ("транспорт", ("метро", "автобус", "электричка", "проезд", "транспорт")),
    (
        "подписки",
        ("кинопоиск", "netflix", "spotify", "яндекс плюс", "подписк", "иви", "okko", "apple music"),
    ),
    ("фитнес", ("фитнес", "спортзал", "тренажер")),
    ("связь", ("мтс", "билайн", "мегафон", "теле2", "связь")),
    ("здоровье", ("аптек", "лекарств", "врач", "клиник")),
    ("одежда", ("одежд", "футболк", "кроссов")),
    ("развлечения", ("кино", "steam", "игр", "развлечен")),
    ("жилье", ("аренда", "жкх", "квартир", "жилье")),
)

_KEYWORDS: tuple[tuple[str, str], ...] = tuple(
    sorted(
        ((word.replace("ё", "е"), category) for category, words in _RULES for word in words),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)


def _fold(text: str) -> str:
    return " ".join(text.strip().lower().replace("ё", "е").split())


def categorize(title: str) -> str:
    folded = _fold(title)
    if folded in CATEGORY_ORDER:
        return folded
    for word, category in _KEYWORDS:
        if word in folded:
            return category
    return "прочее"


def resolve_category(raw: str) -> str:
    folded = _fold(raw)
    if not folded:
        return ""
    if folded in CATEGORY_ORDER:
        return folded
    guessed = categorize(folded)
    if guessed != "прочее":
        return guessed
    return folded


def breaks_challenge(challenge_category: str, expense_category: str, title: str) -> bool:
    needle = _fold(challenge_category)
    if not needle:
        return False
    if needle == expense_category:
        return True
    if len(needle) >= 3 and needle in _fold(title):
        return True
    return False


def category_list() -> str:
    return ", ".join(CATEGORY_ORDER)
