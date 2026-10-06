from __future__ import annotations

import os
from pathlib import Path

import pytest

from egrocery.config import get_basket_path, get_location_path, get_store_root


def test_store_paths_use_job_agent_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    store = tmp_path / "store"
    store.mkdir()
    monkeypatch.setenv("JOB_AGENT_STORE", str(store))
    monkeypatch.delenv("EGROCERY_STORE", raising=False)
    assert get_store_root() == store
    assert get_location_path() == store / "docs/e-grocery-location.yaml"
    assert get_basket_path() == store / "docs/e-grocery-basket-starter.yaml"


def test_egrocery_store_overrides_job_agent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JOB_AGENT_STORE", str(tmp_path / "job"))
    monkeypatch.setenv("EGROCERY_STORE", str(tmp_path / "eg"))
    assert get_store_root() == tmp_path / "eg"
