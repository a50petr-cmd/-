from __future__ import annotations

import re

from job_agent.models import ScoredVacancy, Vacancy
from job_agent.profile import SearchProfile


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def _blob(v: Vacancy) -> str:
    return _norm(" ".join([v.title, v.company, v.description, v.area or ""]))


def _experience_keywords(profile: SearchProfile) -> list[str]:
    if profile.experience_keywords:
        return [k.lower() for k in profile.experience_keywords if k]
    combined = list(profile.must_have or []) + list(profile.nice_to_have or [])
    if combined:
        return [k.lower() for k in combined if k]
    return [s.lower() for s in profile.skills if s]


def _role_match(profile: SearchProfile, text: str) -> str | None:
    for role in profile.desired_roles:
        norm = _norm(role)
        if len(norm) >= 8 and norm[: min(20, len(norm))] in text:
            return role
        parts = [p for p in re.split(r"[\s/()]+", norm) if len(p) > 4]
        hits = sum(1 for p in parts if p in text)
        if hits >= 2 or (len(parts) == 1 and parts[0] in text):
            return role
    return None


def score_vacancy(profile: SearchProfile, vacancy: Vacancy) -> ScoredVacancy:
    text = _blob(vacancy)
    score = 45
    reasons: list[str] = []

    exclude = profile.exclude or []
    for ex in exclude:
        if ex and ex.lower() in text:
            score -= 25
            reasons.append(f"исключение «{ex}»")

    exp_keys = _experience_keywords(profile)
    matched_exp = [k for k in exp_keys if k in text]
    min_hits = max(1, profile.experience_min_hits)
    if matched_exp:
        score += min(40, len(matched_exp) * 6)
        reasons.append(f"опыт: {', '.join(matched_exp[:6])}")
        if len(matched_exp) < min_hits:
            score -= 8
            reasons.append(f"мало маркеров опыта (<{min_hits})")
    else:
        score -= 20
        reasons.append("нет совпадений с опытом")

    leadership = (
        "директор",
        "руководит",
        "head of",
        " c-level",
        " ceo",
        " coo",
        "коммерческ",
        "операцион",
        "исполнительн",
        "генеральн",
        "заместител",
        "vice president",
        " vp ",
    )
    if any(m in text for m in leadership):
        score += 8
        reasons.append("уровень руководства")

    role = _role_match(profile, text)
    if role:
        score += 7
        reasons.append(f"близкая роль: {role[:50]}")

    if profile.experience_years and profile.experience_years >= 10:
        senior_markers = ("от 10 лет", "10+ лет", "более 10", "senior", "15 лет", "от 5 лет")
        junior_markers = ("без опыта", "от 1 года", "1–3 года", "1-3 года", "junior", "стажёр")
        if any(m in text for m in senior_markers):
            score += 5
            reasons.append("опыт 10+ в вакансии")
        if any(m in text for m in junior_markers):
            score -= 12
            reasons.append("уровень junior/мало опыта")

    if profile.salary_min_rub and vacancy.salary_to:
        if vacancy.salary_to >= profile.salary_min_rub:
            score += 7
            reasons.append("зарплата в вилке")
        elif vacancy.salary_to < profile.salary_min_rub * 0.7:
            score -= 10
            reasons.append("зарплата ниже ожиданий")

    remote_words = ("удалён", "remote", "дистанцион", "гибрид", "hybrid")
    if profile.remote_preference in ("remote", "hybrid_or_remote"):
        if any(w in text for w in remote_words):
            score += 5
            reasons.append("формат remote/hybrid")

    score = max(0, min(100, score))
    rationale = "; ".join(reasons) if reasons else "базовая оценка по заголовку и описанию"
    return ScoredVacancy(vacancy=vacancy, score=score, rationale=rationale)


def score_all(profile: SearchProfile, vacancies: list[Vacancy]) -> list[ScoredVacancy]:
    scored = [score_vacancy(profile, v) for v in vacancies]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored
