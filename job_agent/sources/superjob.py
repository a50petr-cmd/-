from __future__ import annotations

import logging

import requests

from job_agent.config import SUPERJOB_API_BASE, SUPERJOB_APP_ID
from job_agent.models import Vacancy
from job_agent.profile import SearchProfile
from job_agent.sources.base import VacancySource

log = logging.getLogger(__name__)


class SuperjobSource(VacancySource):
    """Опционально: нужен SUPERJOB_APP_ID из https://api.superjob.ru/register/"""

    name = "superjob"

    def fetch(self, profile: SearchProfile, limit: int = 30) -> list[Vacancy]:
        if not SUPERJOB_APP_ID:
            log.info("Superjob пропущен: не задан SUPERJOB_APP_ID")
            return []

        keyword = profile.hh_search_text.split(" OR ")[0] if profile.hh_search_text else "python"
        params = {"keyword": keyword, "count": min(limit, 100)}
        headers = {"X-Api-App-Id": SUPERJOB_APP_ID}
        try:
            self._sleep(0.5)
            resp = requests.get(
                f"{SUPERJOB_API_BASE}/vacancies/",
                params=params,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            log.warning("Superjob API: %s", exc)
            return []

        objects = data.get("objects") or []
        vacancies: list[Vacancy] = []
        for obj in objects[:limit]:
            prof = obj.get("profession") or ""
            payment = obj.get("payment_from"), obj.get("payment_to")
            vacancies.append(
                Vacancy(
                    source=self.name,
                    external_id=str(obj.get("id", "")),
                    title=prof,
                    company=(obj.get("firm_name") or ""),
                    url=obj.get("link") or "",
                    description=(obj.get("vacancyRichText") or obj.get("candidat") or "")[:3000],
                    salary_from=payment[0],
                    salary_to=payment[1],
                    salary_currency="RUR",
                    area=(obj.get("town") or {}).get("title"),
                    published_at=obj.get("date_published"),
                    raw=obj,
                )
            )
        return vacancies
