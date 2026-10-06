from __future__ import annotations

# Stems used in scoring/profile → readable phrases for cover letters (display only).
KEYWORD_DISPLAY_RU: dict[str, str] = {
    "логистик": "логистика",
    "операцион": "операции",
    "операционный": "операционное управление",
    "оптов": "оптовая торговля",
    "управлен": "управление",
    "торгов": "торговля",
    "доставк": "доставка",
    "кросс-функцион": "кросс-функциональное управление",
    "руководитель проект": "руководство проектами",
    "проект": "управление проектами",
    "франчайз": "франчайзинг",
    "маркетплейс": "маркетплейсы",
    "склад": "складская логистика",
    "ритейл": "ритейл",
    "retail": "retail",
    "e-grocery": "e-grocery",
    "b2b": "B2B",
    "импорт": "импорт",
    "darkstore": "dark store",
    "fmcg": "FMCG",
    "e-commerce": "e-commerce",
    "supply": "supply chain",
}


def display_keyword(keyword: str) -> str:
    key = keyword.strip().lower()
    return KEYWORD_DISPLAY_RU.get(key, keyword.strip())


def humanize_score_rationale(rationale: str) -> str:
    """Replace experience keyword stems in scoring rationale for human-readable cover letters."""
    if not rationale:
        return rationale
    parts: list[str] = []
    for segment in rationale.split("; "):
        if segment.startswith("опыт: "):
            raw = segment[6:]
            words = [w.strip() for w in raw.split(",") if w.strip()]
            shown = [display_keyword(w) for w in words]
            parts.append("опыт: " + ", ".join(shown))
        else:
            parts.append(segment)
    return "; ".join(parts)
