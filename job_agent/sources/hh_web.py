from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from job_agent.config import HH_RATE_DELAY_SEC, HH_WEB_BASE, HH_WEB_USER_AGENT
from job_agent.models import Vacancy
from job_agent.profile import SearchProfile
from job_agent.sources.base import VacancySource
from job_agent.sources.hh_queries import hh_search_queries

log = logging.getLogger(__name__)

_VACANCY_ID_RE = re.compile(r"/vacancy/(\d+)")
_SALARY_RE = re.compile(
    r"(?:от\s+)?(\d[\d\s\u202f\u00a0]*)\s*(?:до\s+(\d[\d\s\u202f\u00a0]*))?\s*₽",
    re.IGNORECASE,
)


def _digits(value: str | None) -> int | None:
    if not value:
        return None
    cleaned = re.sub(r"[\s\u202f\u00a0]", "", value)
    return int(cleaned) if cleaned.isdigit() else None


def _parse_salary_from_text(text: str) -> tuple[int | None, int | None]:
    m = _SALARY_RE.search(text)
    if not m:
        return None, None
    return _digits(m.group(1)), _digits(m.group(2))


def _absolute_vacancy_url(href: str) -> str:
    if href.startswith("http"):
        return href.split("?", 1)[0] if "/vacancy/" in href else href
    joined = urljoin(HH_WEB_BASE, href)
    parsed = urlparse(joined)
    if parsed.path.startswith("/vacancy/"):
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return joined


def _parse_vacancy_card(card: Tag, *, listing_url: str) -> Vacancy | None:
    title_el = card.select_one('[data-qa="serp-item__title"]')
    if not title_el:
        return None
    href = title_el.get("href") or ""
    vid_m = _VACANCY_ID_RE.search(href)
    if not vid_m:
        return None
    vid = vid_m.group(1)
    title = title_el.get_text(strip=True) or ""

    employer_el = card.select_one(
        '[data-qa="vacancy-serp__vacancy-employer"], '
        '[data-qa="vacancy-serp__vacancy-employer-text"]'
    )
    company = employer_el.get_text(strip=True) if employer_el else ""

    address_el = card.select_one('[data-qa="vacancy-serp__vacancy-address"]')
    area = address_el.get_text(strip=True) if address_el else None

    card_text = card.get_text(" ", strip=True)
    salary_from, salary_to = _parse_salary_from_text(card_text)

    meta_parts: list[str] = []
    for el in card.select('[data-qa*="compensation"], [data-qa*="work-experience"]'):
        part = el.get_text(" ", strip=True)
        if part and part not in meta_parts:
            meta_parts.append(part)
    description = " ".join(meta_parts) if meta_parts else card_text[:2000]

    url = _absolute_vacancy_url(href)

    return Vacancy(
        source="hh_web",
        external_id=vid,
        title=title,
        company=company,
        url=url,
        description=description,
        salary_from=salary_from,
        salary_to=salary_to,
        salary_currency="RUR" if (salary_from or salary_to) else None,
        area=area,
        raw={"listing_url": listing_url, "href": href},
    )


class HeadHunterWebSource(VacancySource):
    """Публичная выдача hh.ru/search/vacancy (без OAuth и без api.hh.ru)."""

    name = "hh_web"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": HH_WEB_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def _fetch_one_query(
        self,
        profile: SearchProfile,
        text: str,
        limit: int,
        *,
        seen_urls: set[str],
    ) -> list[Vacancy]:
        areas = profile.hh_area_ids or [1]
        params: dict[str, str | int] = {
            "text": text,
            "order_by": "publication_time",
        }
        if len(areas) == 1:
            params["area"] = areas[0]

        vacancies: list[Vacancy] = []
        page = 0
        per_page = 20

        while len(vacancies) < limit:
            params["page"] = page
            url = f"{HH_WEB_BASE}/search/vacancy"
            try:
                self._sleep(HH_RATE_DELAY_SEC)
                resp = self.session.get(url, params=params, headers=self._headers(), timeout=30)
                if resp.status_code in (403, 429):
                    log.warning(
                        "HH сайт вернул %s (часто блокировка IP). "
                        "Запустите search с домашнего ПК или другой сети.",
                        resp.status_code,
                    )
                    break
                resp.raise_for_status()
            except requests.RequestException as exc:
                log.warning("Ошибка HH web: %s", exc)
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select('[data-qa="vacancy-serp__vacancy"]')
            if not cards:
                if page == 0:
                    log.warning(
                        "HH web: нет карточек для запроса «%s…» (капча или вёрстка).",
                        text[:40],
                    )
                break

            listing_url = resp.url
            for card in cards:
                parsed = _parse_vacancy_card(card, listing_url=listing_url)
                if not parsed or not parsed.url or parsed.url in seen_urls:
                    continue
                seen_urls.add(parsed.url)
                vacancies.append(parsed)
                if len(vacancies) >= limit:
                    break

            if len(cards) < per_page:
                break
            page += 1

        return vacancies

    def fetch(self, profile: SearchProfile, limit: int = 30) -> list[Vacancy]:
        queries = hh_search_queries(profile)
        seen_urls: set[str] = set()
        all_vacancies: list[Vacancy] = []
        per_query = max(8, (limit + len(queries) - 1) // len(queries))

        for q in queries:
            if len(all_vacancies) >= limit:
                break
            need = min(per_query, limit - len(all_vacancies))
            batch = self._fetch_one_query(profile, q, need, seen_urls=seen_urls)
            log.info("HH web запрос «%s…»: %d вакансий", q[:50], len(batch))
            all_vacancies.extend(batch)

        return all_vacancies[:limit]
