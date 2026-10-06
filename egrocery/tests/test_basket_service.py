from __future__ import annotations

from pathlib import Path

from egrocery.basket_service import build_basket_markdown
from egrocery.delivery_point import save_user_delivery_point


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
