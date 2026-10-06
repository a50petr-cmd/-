from __future__ import annotations

import os
import time
from typing import Generic, TypeVar

T = TypeVar("T")


class TtlCache(Generic[T]):
    def __init__(self, ttl_seconds: float | None = None) -> None:
        raw = os.environ.get("EGROCERY_SEARCH_CACHE_TTL", "60").strip()
        self._ttl = ttl_seconds if ttl_seconds is not None else float(raw or "60")
        self._store: dict[str, tuple[float, T]] = {}

    def get(self, key: str) -> T | None:
        entry = self._store.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: T) -> None:
        if self._ttl <= 0:
            return
        self._store[key] = (time.monotonic() + self._ttl, value)
