from __future__ import annotations

import json
import logging
from typing import Any

from egrocery.config import get_vkusvill_mcp_url
from egrocery.http_client import ProviderHttpError, shared_http_client
from egrocery.offers import Offer
from egrocery.text_sanitize import clean_product_text

logger = logging.getLogger(__name__)

DEFAULT_MCP_URL = "https://mcp001.vkusvill.ru/mcp"


def _mcp_url() -> str:
    return get_vkusvill_mcp_url() or DEFAULT_MCP_URL


def _mcp_call(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    client = shared_http_client()
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    resp = client.request(
        "POST",
        _mcp_url(),
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    if resp.status_code == 429:
        raise ProviderHttpError("VkusVill MCP: лимит запросов (429)", status=429)
    if resp.status_code >= 400:
        raise ProviderHttpError(
            f"VkusVill MCP HTTP {resp.status_code}", status=resp.status_code
        )
    envelope = resp.json()
    if "error" in envelope:
        raise ProviderHttpError(str(envelope["error"]))
    result = envelope.get("result") or {}
    content = result.get("content") or []
    if not content:
        return {}
    text = content[0].get("text") if isinstance(content[0], dict) else None
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("VkusVill MCP non-JSON tool response")
        return {}
    if isinstance(parsed, dict) and parsed.get("ok") is False:
        err = parsed.get("error") or {}
        msg = err.get("message") if isinstance(err, dict) else str(err)
        raise ProviderHttpError(f"VkusVill API: {msg or 'ошибка'}")
    data = parsed.get("data") if isinstance(parsed, dict) else parsed
    return data if isinstance(data, dict) else {}


def search_products(query: str, *, limit: int = 10) -> list[Offer]:
    data = _mcp_call(
        "vkusvill_products_search",
        {
            "q": query,
            "page": 1,
            "sort": "popularity",
            "mode": "short",
        },
    )
    items = data.get("items") if isinstance(data.get("items"), list) else []
    offers: list[Offer] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        price_obj = item.get("price") or {}
        current = price_obj.get("current") if isinstance(price_obj, dict) else None
        if current is None:
            continue
        try:
            price_rub = float(current)
        except (TypeError, ValueError):
            continue
        name = clean_product_text(str(item.get("name") or "").strip()) or "—"
        url = item.get("url")
        unit = item.get("unit")
        offers.append(
            Offer(
                service="vkusvill",
                product_name=name,
                price_rub=price_rub,
                url=str(url) if url else None,
                quantity_label=str(unit) if unit else None,
                product_id=str(item.get("id") or item.get("xml_id") or ""),
            )
        )
    return offers
