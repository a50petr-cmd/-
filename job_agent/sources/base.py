from __future__ import annotations

import time
from abc import ABC, abstractmethod

from job_agent.models import Vacancy
from job_agent.profile import SearchProfile


class VacancySource(ABC):
    name: str

    @abstractmethod
    def fetch(self, profile: SearchProfile, limit: int = 30) -> list[Vacancy]:
        ...

    def _sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)
