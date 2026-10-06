from __future__ import annotations

import re
from difflib import SequenceMatcher

_STOP_WORDS = {
    "и",
    "в",
    "на",
    "для",
    "с",
    "без",
    "the",
    "a",
    "купить",
    "цена",
    "новый",
    "original",
}


def normalize_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def title_keywords(title: str, max_tokens: int = 8) -> str:
    tokens = [w for w in normalize_title(title).split() if len(w) > 1 and w not in _STOP_WORDS]
    return " ".join(tokens[:max_tokens])


def token_set(title: str) -> set[str]:
    return {w for w in normalize_title(title).split() if len(w) > 1 and w not in _STOP_WORDS}


def match_score(source_title: str, candidate_title: str) -> float:
    a = normalize_title(source_title)
    b = normalize_title(candidate_title)
    if not a or not b:
        return 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    sa, sb = token_set(source_title), token_set(candidate_title)
    if not sa or not sb:
        jaccard = 0.0
    else:
        jaccard = len(sa & sb) / len(sa | sb)
    return 0.45 * seq + 0.55 * jaccard


def match_label(score: float) -> str:
    if score >= 0.82:
        return "то же"
    if score >= 0.55:
        return "похожее"
    return "слабое совпадение"
