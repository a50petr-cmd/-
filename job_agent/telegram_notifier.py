from __future__ import annotations

import logging
from typing import Iterable

import requests

from job_agent.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from job_agent.models import ScoredVacancy

log = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}"


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


def send_message(text: str, *, parse_mode: str = "HTML") -> bool:
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
    payload = {"chat_id": chat_id, "text": text[:4096], "parse_mode": parse_mode, "disable_web_page_preview": False}
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        log.warning("Telegram sendMessage: %s", exc)
        return False


def format_digest(scored: Iterable[ScoredVacancy], threshold: int) -> str:
    lines = [f"<b>Новые вакансии (score ≥ {threshold})</b>", ""]
    for s in scored:
        v = s.vacancy
        lines.append(
            f"• <b>{s.score}</b> — {v.title} ({v.company})\n"
            f"  {v.url}\n"
            f"  <i>{s.rationale[:200]}</i>\n"
            f"  Одобрить: <code>python -m job_agent approve {v.uid}</code>"
        )
    lines.append("\n@PetroAlekseev — проверьте pending в internal/pending-applications/")
    return "\n".join(lines)


def notify_high_scores(scored: list[ScoredVacancy], threshold: int) -> int:
    high = [s for s in scored if s.score >= threshold]
    if not high:
        return 0
    ok = send_message(format_digest(high, threshold))
    return len(high) if ok else 0
