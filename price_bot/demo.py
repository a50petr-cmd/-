from __future__ import annotations

from price_bot.models import ComparisonResult, MatchedListing, Platform, ProductListing


def demo_comparison_for_url(url: str) -> ComparisonResult:
    """Deterministic sample output when marketplaces block datacenter IPs."""
    lower = url.lower()
    if "wildberries" in lower or "ozon" in lower or "market.yandex" in lower:
        source_platform = (
            Platform.WILDBERRIES
            if "wildberries" in lower
            else Platform.OZON
            if "ozon" in lower
            else Platform.YANDEX_MARKET
        )
    else:
        source_platform = Platform.OZON

    canonical_urls = {
        Platform.OZON: "https://www.ozon.ru/product/-123456789/",
        Platform.WILDBERRIES: "https://www.wildberries.ru/catalog/177900896/detail.aspx",
        Platform.YANDEX_MARKET: "https://market.yandex.ru/product--/-43567890",
    }
    if url.startswith("http"):
        canonical_urls[source_platform] = url

    source = ProductListing(
        platform=source_platform,
        product_id="177900896" if source_platform == Platform.WILDBERRIES else "123456789",
        title="Samsung Galaxy Buds2 Pro, беспроводные наушники, graphite",
        price_rub=8990,
        url=canonical_urls[source_platform],
        is_source=True,
    )

    all_matches = [
        MatchedListing(
            platform=Platform.OZON,
            product_id="123456789",
            title="Наушники Samsung Galaxy Buds2 Pro Graphite",
            price_rub=8490,
            url=canonical_urls[Platform.OZON],
            match_score=0.91,
            match_label="то же",
        ),
        MatchedListing(
            platform=Platform.WILDBERRIES,
            product_id="177900896",
            title="Наушники TWS Samsung Galaxy Buds 2 Pro",
            price_rub=8990,
            url=canonical_urls[Platform.WILDBERRIES],
            match_score=0.78,
            match_label="похожее",
        ),
        MatchedListing(
            platform=Platform.YANDEX_MARKET,
            product_id="43567890",
            title="Samsung Galaxy Buds2 Pro, цвет graphite",
            price_rub=9290,
            url=canonical_urls[Platform.YANDEX_MARKET],
            match_score=0.86,
            match_label="то же",
        ),
    ]
    matches = [m for m in all_matches if m.platform != source.platform]
    return ComparisonResult(
        source=source,
        matches=matches,
        errors=["DEMO: реальные запросы к маркетплейсам не выполнялись (PRICE_BOT_DEMO=1)."],
    )
