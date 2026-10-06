from __future__ import annotations

import json
import logging
from pathlib import Path

import requests

from job_agent.config import (
    FIXTURES_DIR,
    HH_API_BASE,
    HH_RATE_DELAY_SEC,
    HH_USER_AGENT,
)
from job_agent.models import Vacancy
from job_agent.profile import SearchProfile
from job_agent.sources.base import VacancySource

log = logging.getLogger(__name__)


class HeadHunterSource(VacancySource):
    name = "hh"

    def __init__(self, session: requests.Session | None = None, use_fixture: bool = False):
        self.session = session or requests.Session()
        self.use_fixture = use_fixture

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": HH_USER_AGENT,
            "HH-User-Agent": HH_USER_AGENT,
            "Accept": "application/json",
        }

    def fetch(self, profile: SearchProfile, limit: int = 30) -> list[Vacancy]:
        if self.use_fixture:
            return self._from_fixture(limit)

        text = profile.hh_search_text or " ".join(profile.desired_roles[:2] or ["python"])
        areas = profile.hh_area_ids or [1]
        per_page = min(100, max(1, limit))
        params: dict[str, str | int] = {
            "text": text,
            "per_page": per_page,
            "order_by": "publication_time",
        }
        if len(areas) == 1:
            params["area"] = areas[0]

        url = f"{HH_API_BASE}/vacancies"
        try:
            self._sleep(HH_RATE_DELAY_SEC)
            resp = self.session.get(url, params=params, headers=self._headers(), timeout=30)
            if resp.status_code == 403:
                log.warning(
                    "HH API вернул 403 (часто блокировка IP/регистрация). "
                    "Будет попытка через сайт hh.ru или запустите search с --hh-web-only с домашней сети."
                )
                return []
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            log.warning("Ошибка HH API: %s — fallback на fixture", exc)
            return self._from_fixture(limit)

        items = data.get("items") or []
        vacancies: list[Vacancy] = []
        for item in items[:limit]:
            salary = item.get("salary") or {}
            vacancies.append(
                Vacancy(
                    source=self.name,
                    external_id=str(item.get("id", "")),
                    title=item.get("name") or "",
                    company=(item.get("employer") or {}).get("name") or "",
                    url=item.get("alternate_url") or "",
                    description=item.get("snippet", {}).get("requirement", "")
                    + " "
                    + item.get("snippet", {}).get("responsibility", ""),
                    salary_from=salary.get("from"),
                    salary_to=salary.get("to"),
                    salary_currency=salary.get("currency"),
                    area=(item.get("area") or {}).get("name"),
                    published_at=item.get("published_at"),
                    raw=item,
                )
            )
        return vacancies

    def _from_fixture(self, limit: int) -> list[Vacancy]:
        path = FIXTURES_DIR / "hh_sample.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("items") or []
        vacancies: list[Vacancy] = []
        for item in items[:limit]:
            salary = item.get("salary") or {}
            vacancies.append(
                Vacancy(
                    source=self.name,
                    external_id=str(item.get("id", "")),
                    title=item.get("name") or "",
                    company=(item.get("employer") or {}).get("name") or "",
                    url=item.get("alternate_url") or "",
                    description=(item.get("snippet") or {}).get("requirement", "")
                    + " "
                    + (item.get("snippet") or {}).get("responsibility", ""),
                    salary_from=salary.get("from"),
                    salary_to=salary.get("to"),
                    salary_currency=salary.get("currency"),
                    area=(item.get("area") or {}).get("name"),
                    published_at=item.get("published_at"),
                    raw=item,
                )
            )
        return vacancies
