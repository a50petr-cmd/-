"""В базе время наивное и всегда UTC. Наивную дату без пояса читаем как UTC."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "Europe/Moscow"


def safe_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def parse_timezone(text: str) -> str | None:
    raw = text.strip()
    folded = raw.lower().replace("ё", "е")
    if folded in {"ок", "ok", "да", "москва", "moscow", "europe/moscow"}:
        return DEFAULT_TIMEZONE
    try:
        ZoneInfo(raw)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return raw


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ensure_naive_utc(moment: datetime) -> datetime:
    if moment.tzinfo is not None:
        return moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


def to_local(moment: datetime, tz_name: str) -> datetime:
    aware = ensure_naive_utc(moment).replace(tzinfo=timezone.utc)
    return aware.astimezone(safe_zone(tz_name))


def start_of_week_utc_naive(moment: datetime, tz_name: str) -> datetime:
    local = to_local(moment, tz_name)
    monday = (local - timedelta(days=local.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return monday.astimezone(timezone.utc).replace(tzinfo=None)


def deadline_reached(started_at: datetime, now: datetime, delay: timedelta) -> bool:
    return ensure_naive_utc(now) >= ensure_naive_utc(started_at) + delay
