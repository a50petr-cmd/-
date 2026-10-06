from __future__ import annotations

import logging

from job_agent.config import SCORE_NOTIFY_THRESHOLD
from job_agent.models import ScoredVacancy, Vacancy
from job_agent.pending import save_pending_application
from job_agent.profile import SearchProfile
from job_agent.scoring import score_all
from job_agent.sources import HabrCareerSource, HeadHunterSource, HeadHunterWebSource, SuperjobSource
from job_agent.telegram_notifier import notify_high_scores

log = logging.getLogger(__name__)


def _fetch_headhunter(
    profile: SearchProfile,
    *,
    limit: int,
    use_hh_fixture: bool,
    hh_web_only: bool,
) -> list:
    if hh_web_only and not use_hh_fixture:
        web = HeadHunterWebSource()
        batch = web.fetch(profile, limit=limit)
        log.info("Источник %s: %d вакансий", web.name, len(batch))
        return batch

    api = HeadHunterSource(use_fixture=use_hh_fixture)
    batch = api.fetch(profile, limit=limit)
    log.info("Источник %s: %d вакансий", api.name, len(batch))
    if batch or use_hh_fixture:
        return batch

    web = HeadHunterWebSource()
    web_batch = web.fetch(profile, limit=limit)
    log.info("Источник %s (fallback после пустого HH API): %d вакансий", web.name, len(web_batch))
    return web_batch


def run_search(
    profile: SearchProfile,
    *,
    limit: int = 25,
    use_hh_fixture: bool = False,
    hh_web_only: bool = False,
    persist_pending_min_score: int = 55,
    notify: bool = True,
) -> list[ScoredVacancy]:
    all_vacancies = []
    try:
        all_vacancies.extend(
            _fetch_headhunter(
                profile,
                limit=limit,
                use_hh_fixture=use_hh_fixture,
                hh_web_only=hh_web_only,
            )
        )
    except Exception as exc:  # noqa: BLE001 — aggregate source errors
        log.exception("HeadHunter упал: %s", exc)

    for src in (HabrCareerSource(), SuperjobSource()):
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
        notify_high_scores(scored, SCORE_NOTIFY_THRESHOLD, profile)

    return scored
