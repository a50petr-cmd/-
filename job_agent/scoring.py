from __future__ import annotations

import re

from job_agent.models import ScoredVacancy, Vacancy
from job_agent.profile import SearchProfile


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def _blob(v: Vacancy) -> str:
    return _norm(" ".join([v.title, v.company, v.description, v.area or ""]))


def score_vacancy(profile: SearchProfile, vacancy: Vacancy) -> ScoredVacancy:
    text = _blob(vacancy)
    score = 50
    reasons: list[str] = []

    must = profile.must_have or [s.lower() for s in profile.skills[:5]]
    nice = profile.nice_to_have or [s.lower() for s in profile.skills[5:]]
    exclude = profile.exclude or []

    matched_must = [k for k in must if k and k in text]
    missing_must = [k for k in must if k and k not in text]
    if must:
        must_ratio = len(matched_must) / len(must)
        score += int(30 * must_ratio)
        if matched_must:
            reasons.append(f"must-have: {', '.join(matched_must[:5])}")
        if missing_must:
            reasons.append(f"нет must-have: {', '.join(missing_must[:5])}")

    matched_nice = [k for k in nice if k and k in text]
    if nice and matched_nice:
        score += min(15, len(matched_nice) * 3)
        reasons.append(f"nice: {', '.join(matched_nice[:5])}")

    for ex in exclude:
        if ex and ex.lower() in text:
            score -= 25
            reasons.append(f"исключение «{ex}»")

    role_hits = [r for r in profile.desired_roles if _norm(r)[:12] in text]
    if role_hits:
        score += 8
        reasons.append(f"роль: {role_hits[0]}")

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
