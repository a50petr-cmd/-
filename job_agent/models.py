from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Vacancy:
    source: str
    external_id: str
    title: str
    company: str
    url: str
    description: str
    salary_from: int | None = None
    salary_to: int | None = None
    salary_currency: str | None = None
    area: str | None = None
    published_at: str | None = None
    raw: dict = field(default_factory=dict)

    @property
    def uid(self) -> str:
        return f"{self.source}:{self.external_id}"


@dataclass
class ScoredVacancy:
    vacancy: Vacancy
    score: int
    rationale: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
