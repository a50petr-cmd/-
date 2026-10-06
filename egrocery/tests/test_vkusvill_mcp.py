from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from egrocery.vkusvill_mcp import search_products


def test_vkusvill_mcp_parses_tool_response() -> None:
    inner = {
        "ok": True,
        "data": {
            "items": [
                {
                    "id": 1,
                    "name": "Молоко",
                    "price": {"current": 99},
                    "url": "https://vkusvill.ru/goods/x/",
                    "unit": "шт",
                }
            ]
        },
    }
    envelope = {
        "result": {
            "content": [{"type": "text", "text": json.dumps(inner)}],
        }
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = envelope
    with patch("egrocery.vkusvill_mcp.shared_http_client") as client_factory:
        client = MagicMock()
        client.request.return_value = mock_resp
        client_factory.return_value = client
        offers = search_products("молоко")
    assert len(offers) == 1
    assert offers[0].price_rub == 99.0
    assert offers[0].product_name == "Молоко"
