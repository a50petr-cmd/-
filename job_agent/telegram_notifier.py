from __future__ import annotations

import html
import logging
from typing import Iterable

import requests

from job_agent.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_INCLUDE_COVER_LETTERS
from job_agent.cover_letter import generate_cover_letter
from job_agent.models import ScoredVacancy
from job_agent.pending import load_pending
from job_agent.profile import SearchProfile

log = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}"
MAX_LEN = 4096


def resolve_chat_id_from_updates(token: str) -> str | None:
    """После /start пользователь появится в getUpdates — сохраните chat.id в TELEGRAM_CHAT_ID."""
    url = f"{API_BASE.format(token=token)}/getUpdates"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        log.warning("Telegram getUpdates: %s", exc)
        return None
    for upd in reversed(data.get("result") or []):
        msg = upd.get("message") or upd.get("edited_message")
        if msg and msg.get("chat", {}).get("id"):
            return str(msg["chat"]["id"])
    return None


def send_message(text: str, *, parse_mode: str | None = "HTML") -> bool:
    if not TELEGRAM_BOT_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN не задан — уведомление пропущено")
        return False
    chat_id = TELEGRAM_CHAT_ID or resolve_chat_id_from_updates(TELEGRAM_BOT_TOKEN)
    if not chat_id:
        log.warning(
            "TELEGRAM_CHAT_ID не задан и chat не найден в getUpdates. "
            "Напишите боту /start и задайте TELEGRAM_CHAT_ID."
        )
        return False
    url = f"{API_BASE.format(token=TELEGRAM_BOT_TOKEN)}/sendMessage"
    payload: dict = {
        "chat_id": chat_id,
        "text": text[:MAX_LEN],
        "disable_web_page_preview": False,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        log.warning("Telegram sendMessage: %s", exc)
        return False


def _chunk_pre(text: str, header_html: str, *, max_body: int = 3400) -> list[str]:
    """Сообщения с <pre> для удобного копирования письма."""
    chunks: list[str] = []
    body = text
    first = True
    while body:
        part = body[:max_body]
        body = body[max_body:]
        suffix = "\n\n… (продолжение)" if body else ""
        prefix = header_html if first else header_html + " <i>(продолжение)</i>\n"
        first = False
        chunks.append(f"{prefix}<pre>{html.escape(part)}{suffix}</pre>")
    return chunks


def format_digest(scored: Iterable[ScoredVacancy], threshold: int) -> str:
    lines = [f"<b>Новые вакансии (score ≥ {threshold})</b>", ""]
    for s in scored:
        v = s.vacancy
        lines.append(
            f"• <b>{s.score}</b> — {html.escape(v.title)} ({html.escape(v.company)})\n"
            f"  {v.url}\n"
            f"  <i>{html.escape(s.rationale[:180])}</i>"
        )
    if TELEGRAM_INCLUDE_COVER_LETTERS:
        lines.append("\n<b>Сопроводительные письма</b> — в следующих сообщениях (блок <pre>, удобно копировать).")
    else:
        lines.append("\nПисьма: <code>python -m job_agent pending</code>")
    return "\n".join(lines)


def _cover_letter_for(profile: SearchProfile, s: ScoredVacancy) -> str:
    pending = load_pending(s.vacancy.uid)
    if pending and pending.get("cover_letter_ru"):
        return str(pending["cover_letter_ru"])
    return generate_cover_letter(profile, s.vacancy, s.rationale)


def format_vacancy_with_letter(profile: SearchProfile, s: ScoredVacancy) -> list[str]:
    v = s.vacancy
    letter = _cover_letter_for(profile, s)
    header = (
        f"<b>📋 Сопроводительное</b> (score {s.score})\n"
        f"<b>{html.escape(v.title)}</b> — {html.escape(v.company)}\n"
        f"{v.url}\n\n"
    )
    return _chunk_pre(letter, header)


def notify_high_scores(
    scored: list[ScoredVacancy],
    threshold: int,
    profile: SearchProfile | None = None,
) -> int:
    high = [s for s in scored if s.score >= threshold]
    if not high:
        return 0
    ok = send_message(format_digest(high, threshold))
    if not ok:
        return 0

    if TELEGRAM_INCLUDE_COVER_LETTERS and profile:
        for s in high:
            for msg in format_vacancy_with_letter(profile, s):
                if not send_message(msg):
                    log.warning("Не удалось отправить письмо для %s", s.vacancy.uid)
                    break

    return len(high)


def _scored_from_pending(data: dict) -> ScoredVacancy:
    from job_agent.models import Vacancy

    v = data["vacancy"]
    vacancy = Vacancy(
        source=v.get("source", ""),
        external_id=str(v.get("external_id", "")),
        title=v.get("title", ""),
        company=v.get("company", ""),
        url=v.get("url", ""),
        description="",
        salary_from=v.get("salary_from"),
        salary_to=v.get("salary_to"),
        area=v.get("area"),
    )
    return ScoredVacancy(
        vacancy=vacancy,
        score=int(data.get("score", 0)),
        rationale=str(data.get("rationale", "")),
    )


def send_pending_cover_letter(uid: str, profile: SearchProfile) -> bool:
    """Отправить cover_letter_ru из pending в Telegram (удобно копировать из <pre>)."""
    pending = load_pending(uid)
    if not pending:
        log.warning("pending не найден: %s", uid)
        return False
    scored = _scored_from_pending(pending)
    ok = True
    for msg in format_vacancy_with_letter(profile, scored):
        if not send_message(msg):
            ok = False
    return ok
