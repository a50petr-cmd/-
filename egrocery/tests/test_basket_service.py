from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from egrocery.basket_service import build_basket_markdown
from egrocery.delivery_point import save_user_delivery_point, user_yaml_path


def _seed_store(store: Path) -> None:
    docs = store / "docs"
    docs.mkdir(parents=True)
    (docs / "e-grocery-location.yaml").write_text(
        """
city: Электросталь
region: Московская область
country: RU
services_enabled: [samokat, yandex_lavka, vkusvill]
services_deferred: [ozon_fresh]
""".strip(),
        encoding="utf-8",
    )
    (docs / "e-grocery-basket-starter.yaml").write_text(
        """
name: test-basket
items:
  - id: milk
    label: Молоко
    query: milk
""".strip(),
        encoding="utf-8",
    )


def test_basket_header_includes_delivery_point(
    monkeypatch, tmp_path: Path
) -> None:
    store = tmp_path / "store"
    store.mkdir()
    _seed_store(store)
    monkeypatch.setenv("JOB_AGENT_STORE", str(store))
    save_user_delivery_point(
        store,
        1001,
        address_text="Электросталь, ул. Тест",
        lat=55.78,
        lon=38.44,
    )
    text = build_basket_markdown(chat_id=1001)
    assert "Точка доставки" in text
    assert "55.78000" in text or "55.78" in text
    assert "chat_id: 1001" in text


def test_basket_retries_geocode_when_coords_missing(
    monkeypatch, tmp_path: Path
) -> None:
    store = tmp_path / "store"
    store.mkdir()
    _seed_store(store)
    monkeypatch.delenv("YANDEX_GEOCODER_API_KEY", raising=False)
    monkeypatch.setenv("JOB_AGENT_STORE", str(store))
    save_user_delivery_point(
        store,
        2002,
        address_text="Электросталь, Ялагина 13",
        geocode_warning="нет координат",
    )
    payload = [
        {
            "lat": "55.78400",
            "lon": "38.44600",
            "display_name": "Ялагина, Электросталь",
            "address": {"city": "Электросталь"},
        }
    ]
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    with patch("egrocery.geocode.urllib.request.urlopen", return_value=mock_resp):
        text = build_basket_markdown(chat_id=2002)
    assert "55.78400" in text or "55.784" in text
    doc_path = user_yaml_path(store, 2002)
    saved = doc_path.read_text(encoding="utf-8")
    assert "lat:" in saved
    assert "55.784" in saved
