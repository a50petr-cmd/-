from __future__ import annotations

from job_agent.display_ru import display_keyword, humanize_rationale_for_cover
from job_agent.models import Vacancy
from job_agent.profile import SearchProfile


def generate_cover_letter(profile: SearchProfile, vacancy: Vacancy, score_rationale: str = "") -> str:
    if profile.skills:
        skills_line = ", ".join(display_keyword(s) for s in profile.skills[:8])
    else:
        skills_line = "мой стек из резюме"
    roles = ", ".join(profile.desired_roles[:2]) if profile.desired_roles else "инженерная роль"
    exp = (
        f"Опыт около {profile.experience_years} лет."
        if profile.experience_years
        else "Опыт и детали — в приложенном резюме."
    )
    salary = (
        f"Ожидания по доходу: от {profile.salary_min_rub:,} ₽ gross."
        .replace(",", " ")
        if profile.salary_min_rub
        else (profile.salary_comment or "Готов обсудить уровень дохода на интервью.")
    )
    location = profile.location or "РФ"
    rationale_human = humanize_rationale_for_cover(score_rationale)
    match_note = f"\n\nПочему откликаюсь: {rationale_human}." if rationale_human else ""

    return f"""Здравствуйте!

Меня зовут {profile.full_name}, интересуюсь позицией «{vacancy.title}» в {vacancy.company or 'вашей компании'}.
Целевые роли: {roles}. {exp}

Ключевые навыки: {skills_line}.
Локация: {location}. Формат работы: {profile.remote_preference.replace('_', ' ')}.
{salary}

Буду рад обсудить, как мой опыт поможет вашей команде. Резюме приложено; связь удобнее через Telegram {profile.telegram}.{match_note}

С уважением,
{profile.full_name}
"""
