from __future__ import annotations

from egrocery.config import get_vkusvill_mcp_url


def search_products(query: str, limit: int = 3) -> list[dict[str, str]]:
    """
    P0 stub: real search needs VKUSVILL_MCP_URL (see https://mcp.vkusvill.ru/).

    Set env VKUSVILL_MCP_URL to the MCP endpoint when available; until then returns
    no results and callers should keep manual SKU placeholders.
    """
    _ = limit
    if not get_vkusvill_mcp_url():
        return []
    # HTTP/MCP client — P1; P0 leaves cells as manual placeholders.
    raise NotImplementedError(
        "VkusVill MCP client not implemented in P0; set prices manually or extend "
        "egrocery.vkusvill_mcp when VKUSVILL_MCP_URL is configured."
    )
