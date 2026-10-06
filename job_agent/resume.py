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

    first_line = text.strip().split("\n", 1)[0].strip()
    if re.match(r"^[А-ЯA-Z][а-яa-z]+(?:\s+[А-ЯA-Z][а-яa-z]+){1,3}$", first_line):
        profile.full_name = first_line

    loc_m = re.search(r"Проживает:\s*([^\n]+)", text)
    if not loc_m:
        loc_m = re.search(r"(?:Город|Location|Локация)[:\s]+([^\n,]+)", text, re.IGNORECASE)
    if loc_m:
        profile.location = loc_m.group(1).strip()

    role_m = re.search(
        r"Желаемая должность[^\n]*\n([^\n]+)",
        text,
        re.IGNORECASE,
    )
    if role_m:
        primary_role = role_m.group(1).strip()
        if primary_role and "зарплат" not in primary_role.lower():
            profile.desired_roles = [primary_role]

    spec_m = re.search(r"Специализации:\s*\n?\s*[—\-]?\s*([^\n]+)", text)
    if spec_m:
        spec = spec_m.group(1).strip()
        if spec and spec not in profile.desired_roles:
            profile.desired_roles.append(spec)

    # Дополнительные целевые формулировки по опыту (HH / SuperJob)
    role_aliases = [
        "Операционный директор",
        "COO",
        "Руководитель проектов",
        "Директор по операциям",
        "Head of Operations",
    ]
    for alias in role_aliases:
        if alias.lower() in text.lower() and alias not in profile.desired_roles:
            profile.desired_roles.append(alias)

    salary = _find_int(r"(?:зарплат|salary|ожидан)[^\d]{0,20}(\d[\d\s]{3,})", text)
    if salary:
        profile.salary_min_rub = salary

    exp_m = re.search(r"Опыт работы\s*[—\-]\s*(\d+)\s*лет", text, re.IGNORECASE)
    if exp_m:
        profile.experience_years = int(exp_m.group(1))
    else:
        exp = _find_int(r"(\d+)\+?\s*(?:лет|years).*?(?:опыт|experience)", text)
        if exp:
            profile.experience_years = exp

    mgmt_keywords = re.findall(
        r"(?i)\b(операционн(?:ый|ого|ая|ое)|coo|e-grocery|darkstore|логистик|"
        r"кросс-функцион|b2b|retail|ритейл|франчайз|supply chain|"
        r"управление проект|директор|руководитель проект)\w*",
        text,
    )
    tech_keywords = re.findall(
        r"\b(Python|JavaScript|TypeScript|Go|Golang|Java|SQL|PostgreSQL|"
        r"Docker|Kubernetes|FastAPI|Django|DevOps|Backend|Frontend)\b",
        text,
        re.IGNORECASE,
    )
    raw_skills = {k.lower() for k in mgmt_keywords if len(k) > 3} | {
        s.capitalize() for s in tech_keywords
    }
    profile.skills = sorted(raw_skills)[:25]

    if profile.desired_roles:
        profile.must_have = [
            "операцион",
            "директор",
        ]
        profile.nice_to_have = [
            "coo",
            "руководитель проект",
            "логистик",
            "ритейл",
            "e-grocery",
            "b2b",
            "кросс-функцион",
            "darkstore",
            "франчайз",
        ]
        profile.hh_search_text = (
            '"операционный директор" OR COO OR "директор по операциям" '
            'OR "руководитель операционных проектов" OR "head of operations"'
        )
        profile.habr_query = "operations"
    elif tech_keywords:
        profile.desired_roles = ["Backend-разработчик", "Python-разработчик"]
        profile.must_have = [s.lower() for s in profile.skills[:5]]
        profile.nice_to_have = [s.lower() for s in profile.skills[5:15]]
        profile.hh_search_text = " OR ".join(profile.skills[:4])
        profile.habr_query = profile.skills[0].lower() if profile.skills else "python"

    profile.exclude = [
        "стажёр",
        "intern",
        "без опыта",
        "junior python",
        "middle python",
        "разработчик python",
    ]
    profile.hh_area_ids = [1]  # Москва (из резюме)

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
