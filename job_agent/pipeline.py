from __future__ import annotations

import logging

from job_agent.config import SCORE_NOTIFY_THRESHOLD
from job_agent.models import ScoredVacancy
from job_agent.pending import save_pending_application
from job_agent.profile import SearchProfile
from job_agent.scoring import score_all
from job_agent.sources import HabrCareerSource, HeadHunterSource, SuperjobSource
from job_agent.telegram_notifier import notify_high_scores

log = logging.getLogger(__name__)


def run_search(
    profile: SearchProfile,
    *,
    limit: int = 25,
    use_hh_fixture: bool = False,
    persist_pending_min_score: int = 55,
    notify: bool = True,
) -> list[ScoredVacancy]:
    sources = [
        HeadHunterSource(use_fixture=use_hh_fixture),
        HabrCareerSource(),
        SuperjobSource(),
    ]
    all_vacancies = []
    for src in sources:
        try:
            batch = src.fetch(profile, limit=limit)
            log.info("Источник %s: %d вакансий", src.name, len(batch))
            all_vacancies.extend(batch)
        except Exception as exc:  # noqa: BLE001 — aggregate source errors
            log.exception("Источник %s упал: %s", getattr(src, "name", src), exc)

    # dedupe by url
    seen: set[str] = set()
    unique = []
    for v in all_vacancies:
        key = v.url or v.uid
        if key in seen:
            continue
        seen.add(key)
        unique.append(v)

    scored = score_all(profile, unique)

    for s in scored:
        if s.score >= persist_pending_min_score:
            save_pending_application(profile, s)

    if notify:
        notify_high_scores(scored, SCORE_NOTIFY_THRESHOLD)

    return scored
