from __future__ import annotations

# Substrings from experience_keywords / skills → readable Russian in cover letters.
STEM_DISPLAY: dict[str, str] = {
    "логистик": "логистика",
    "доставк": "доставка",
    "управлен": "управление",
    "операцион": "операции",
    "операционный": "операционный менеджмент",
    "оптов": "опт",
    "торгов": "торговля",
    "кросс-функцион": "кросс-функциональное управление",
    "франчайз": "франчайзинг",
    "проект": "управление проектами",
    "руководитель проект": "управление проектами",
    "ритейл": "ритейл",
    "маркетплейс": "маркетплейсы",
    "склад": "складская логистика",
    "импорт": "импорт",
    "b2b": "B2B",
    "fmcg": "FMCG",
    "e-commerce": "e-commerce",
    "e-grocery": "e-grocery",
    "darkstore": "dark store",
    "ebitda": "EBITDA",
    "supply": "supply chain",
}


def display_term(term: str) -> str:
    raw = term.strip()
    if not raw:
        return raw
    key = raw.lower()
    if key in STEM_DISPLAY:
        return STEM_DISPLAY[key]
    for stem, label in sorted(STEM_DISPLAY.items(), key=lambda x: -len(x[0])):
        if key == stem or (len(stem) >= 4 and key.startswith(stem)):
            return label
    return raw


def humanize_skills(skills: list[str], *, limit: int = 8) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for s in skills[:limit]:
        label = display_term(s)
        norm = label.lower()
        if norm in seen:
            continue
        seen.add(norm)
        out.append(label)
    return ", ".join(out) if out else "мой стек из резюме"


def humanize_rationale_for_cover(rationale: str) -> str:
    if not rationale:
        return rationale
    parts: list[str] = []
    for part in (p.strip() for p in rationale.split(";")):
        if part.lower().startswith("опыт:"):
            rest = part.split(":", 1)[1].strip()
            keywords = [display_term(k) for k in rest.split(",")]
            parts.append("опыт: " + ", ".join(keywords))
        else:
            parts.append(part)
    return "; ".join(parts)


# Aliases used by cover_letter
display_keyword = display_term
humanize_score_rationale = humanize_rationale_for_cover
