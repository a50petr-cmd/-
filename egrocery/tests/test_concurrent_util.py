import time

from egrocery.concurrent_util import run_parallel


def test_run_parallel_returns_on_timeout() -> None:
    started = time.monotonic()

    def slow() -> str:
        time.sleep(5)
        return "ok"

    out = run_parallel({"a": slow}, max_workers=1, wall_timeout_sec=0.2)
    elapsed = time.monotonic() - started
    assert out["a"] is None
    assert elapsed < 2.0
