from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

from job_agent.config import HABR_BASE, HABR_RATE_DELAY_SEC
from job_agent.models import Vacancy
from job_agent.profile import SearchProfile
from job_agent.sources.base import VacancySource

log = logging.getLogger(__name__)

# Публичный HTML career.habr.com (без логина). API v1/v2 требует авторизацию.
# Паттерн: карточки с классом vacancy-card и ссылками /vacancies/{id}


class HabrCareerSource(VacancySource):
    name = "habr"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", "PetroJobAgent/1.0 (+https://github.com)")

    def fetch(self, profile: SearchProfile, limit: int = 30) -> list[Vacancy]:
        query = profile.habr_query or (profile.skills[0].lower() if profile.skills else "python")
        url = f"{HABR_BASE}/vacancies?q={quote_plus(query)}&sort=date&type=all"
        self._sleep(HABR_RATE_DELAY_SEC)
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.warning("Habr Career недоступен: %s", exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("div.vacancy-card")
        vacancies: list[Vacancy] = []
        seen: set[str] = set()

        for card in cards:
            link = card.select_one("a.vacancy-card__title-link, a.vacancy-card__backdrop-link")
            if not link or not link.get("href"):
                continue
            href = link["href"]
            vid_m = re.search(r"/vacancies/(\d+)", href)
            if not vid_m:
                continue
            vid = vid_m.group(1)
            if vid in seen:
                continue
            seen.add(vid)

            title_el = card.select_one(".vacancy-card__title")
            title = (title_el.get_text(strip=True) if title_el else link.get_text(strip=True)) or ""
            company_el = card.select_one(".vacancy-card__company-title, .vacancy-card__meta-company")
            company = company_el.get_text(strip=True) if company_el else ""

            meta = card.get_text(" ", strip=True)
            vacancies.append(
                Vacancy(
                    source=self.name,
                    external_id=vid,
                    title=title,
                    company=company,
                    url=urljoin(HABR_BASE, href),
                    description=meta[:2000],
                    raw={"listing_url": url},
                )
            )
            if len(vacancies) >= limit:
                break

        return vacancies
