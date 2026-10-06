from __future__ import annotations

import json
import re
from pathlib import Path

from job_agent.config import AUTO_APPLY, PENDING_DIR
from job_agent.cover_letter import generate_cover_letter
from job_agent.models import ScoredVacancy, utc_now_iso
from job_agent.profile import SearchProfile


def _safe_id(uid: str) -> str:
    return re.sub(r"[^\w\-:.]", "_", uid)[:120]


def pending_path(uid: str) -> Path:
    return PENDING_DIR / f"{_safe_id(uid)}.json"


def load_pending(uid: str) -> dict | None:
    path = pending_path(uid)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_pending() -> list[dict]:
    if not PENDING_DIR.exists():
        return []
    items: list[dict] = []
    for path in sorted(PENDING_DIR.glob("*.json")):
        try:
            items.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    items.sort(key=lambda x: x.get("score", 0), reverse=True)
    return items


def save_pending_application(
    profile: SearchProfile,
    scored: ScoredVacancy,
    *,
    status: str = "pending_approval",
) -> Path:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    letter = generate_cover_letter(profile, scored.vacancy, scored.rationale)
    payload = {
        "id": scored.vacancy.uid,
        "status": status,
        "score": scored.score,
        "rationale": scored.rationale,
        "created_at": utc_now_iso(),
        "approved_at": None,
        "auto_apply_blocked": not AUTO_APPLY,
        "vacancy": {
            "source": scored.vacancy.source,
            "external_id": scored.vacancy.external_id,
            "title": scored.vacancy.title,
            "company": scored.vacancy.company,
            "url": scored.vacancy.url,
            "area": scored.vacancy.area,
            "salary_from": scored.vacancy.salary_from,
            "salary_to": scored.vacancy.salary_to,
        },
        "cover_letter_ru": letter,
        "approval_hint": (
            "Одобрить: python -m job_agent approve "
            + scored.vacancy.uid
            + "  (отклик НЕ отправляется без approve и без JOB_AGENT_AUTO_APPLY=1)"
        ),
    }
    path = pending_path(scored.vacancy.uid)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def approve(uid: str) -> dict:
    data = load_pending(uid)
    if not data:
        raise FileNotFoundError(f"Нет pending-заявки: {uid}")
    if not AUTO_APPLY:
        data["status"] = "approved_manual_apply"
        data["approved_at"] = utc_now_iso()
        data["next_step"] = (
            "Откройте vacancy.url в браузере и отправьте cover_letter_ru вручную "
            "или запустите playwright apply (см. job_agent/apply/README.md)."
        )
    else:
        data["status"] = "approved_auto_apply_requested"
        data["approved_at"] = utc_now_iso()
        data["next_step"] = "AUTO_APPLY включён — выполните job_agent apply (stub) локально с вашей сессией HH."
    pending_path(uid).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data
