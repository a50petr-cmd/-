from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SearchProfile:
    full_name: str = "Петр Алексеев"
    telegram: str = "@PetroAlekseev"
    location: str = ""
    desired_roles: list[str] = field(default_factory=list)
    must_have: list[str] = field(default_factory=list)
    nice_to_have: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    experience_years: int | None = None
    salary_min_rub: int | None = None
    salary_comment: str = ""
    remote_preference: str = "hybrid_or_remote"  # onsite | hybrid | remote | any
    hh_search_text: str = ""
    hh_area_ids: list[int] = field(default_factory=lambda: [1])  # Москва по умолчанию
    habr_query: str = ""
    resume_source_note: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SearchProfile:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict

        return asdict(self)


def load_profile(path: Path) -> SearchProfile:
    if not path.exists():
        raise FileNotFoundError(f"Профиль не найден: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return SearchProfile.from_dict(data)


def save_profile(path: Path, profile: SearchProfile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(profile.to_dict(), f, allow_unicode=True, sort_keys=False)
