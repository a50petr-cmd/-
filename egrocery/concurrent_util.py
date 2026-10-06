from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Callable, TypeVar

T = TypeVar("T")


def run_parallel(
    jobs: dict[str, Callable[[], T]],
    *,
    max_workers: int,
    wall_timeout_sec: float,
) -> dict[str, T | None]:
    """Run jobs in parallel; return partial results on timeout (does not block on stragglers)."""
    if not jobs:
        return {}
    out: dict[str, T | None] = {key: None for key in jobs}
    pool = ThreadPoolExecutor(max_workers=max_workers)
    futures: dict[Future[T], str] = {
        pool.submit(fn): key for key, fn in jobs.items()
    }
    try:
        for fut in as_completed(futures, timeout=wall_timeout_sec):
            key = futures[fut]
            try:
                out[key] = fut.result(timeout=0.1)
            except Exception:
                out[key] = None
    except Exception:
        pass
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return out
