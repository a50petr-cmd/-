from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from job_agent.profile import SearchProfile, save_profile


def extract_pdf_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        parts.append(text)
    return "\n".join(parts).strip()


def _find_int(pattern: str, text: str) -> int | None:
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return None
    digits = re.sub(r"\D", "", m.group(1))
    return int(digits) if digits else None


def _guess_list(section: str, text: str, max_items: int = 20) -> list[str]:
    block = re.search(rf"{section}[:\s]*(.{{0,800}})", text, re.IGNORECASE | re.DOTALL)
    if not block:
        return []
    chunk = block.group(1)
    items = re.split(r"[,;\n•·\-–—]", chunk)
    cleaned = []
    for item in items:
        s = item.strip(" \t\r.")
        if 2 <= len(s) <= 80 and not s.isdigit():
            cleaned.append(s)
    return cleaned[:max_items]


def infer_profile_from_resume_text(text: str, pdf_path: Path) -> SearchProfile:
    """Best-effort heuristics; user should review job-search-profile.md after."""
    profile = SearchProfile(
        resume_source_note=f"Извлечено из PDF: {pdf_path}",
    )

    name_m = re.match(r"^([А-ЯA-Z][а-яa-z]+(?:\s+[А-ЯA-Z][а-яa-z]+)+)", text.strip())
    if name_m:
        profile.full_name = name_m.group(1).strip()

    loc_m = re.search(
        r"(?:Город|Location|Локация)[:\s]+([^\n,]+)",
        text,
        re.IGNORECASE,
    )
    if loc_m:
        profile.location = loc_m.group(1).strip()

    salary = _find_int(r"(?:зарплат|salary|ожидан)[^\d]{0,20}(\d[\d\s]{3,})", text)
    if salary:
        profile.salary_min_rub = salary

    exp = _find_int(r"(\d+)\+?\s*(?:лет|years).*?(?:опыт|experience)", text)
    if exp:
        profile.experience_years = exp

    skill_keywords = re.findall(
        r"\b(Python|JavaScript|TypeScript|Go|Golang|Java|C\+\+|SQL|PostgreSQL|"
        r"Docker|Kubernetes|AWS|GCP|Azure|FastAPI|Django|Flask|React|Vue|Node\.js|"
        r"Linux|Git|CI/CD|ML|Machine Learning|Data Science|Backend|Frontend|DevOps|"
        r"Product Manager|PM|Аналитик|QA|Тестиров)\b",
        text,
        re.IGNORECASE,
    )
    profile.skills = sorted({s if s[0].isupper() else s.capitalize() for s in skill_keywords})

    roles = _guess_list("(?:Желаемая должность|Desired role|Цель)", text)
    if roles:
        profile.desired_roles = roles
    elif profile.skills:
        profile.desired_roles = ["Backend-разработчик", "Python-разработчик"]

    profile.must_have = [s.lower() for s in profile.skills[:5]]
    profile.nice_to_have = [s.lower() for s in profile.skills[5:15]]
    profile.exclude = ["стажёр", "intern", "без опыта", "1c", "1с"]

    if profile.skills:
        profile.hh_search_text = " OR ".join(profile.skills[:4])
        profile.habr_query = profile.skills[0].lower()

    return profile


def analyze_resume_pdf(pdf_path: Path, profile_yaml: Path) -> tuple[SearchProfile, str]:
    if not pdf_path.exists():
        raise FileNotFoundError(f"Резюме PDF не найдено: {pdf_path}")
    text = extract_pdf_text(pdf_path)
    if len(text) < 50:
        raise ValueError("Не удалось извлечь достаточно текста из PDF — возможно, скан без OCR.")
    profile = infer_profile_from_resume_text(text, pdf_path)
    save_profile(profile_yaml, profile)
    return profile, text
