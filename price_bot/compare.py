from __future__ import annotations

from price_bot.config import DEMO_MODE
from price_bot.demo import demo_comparison_for_url
from price_bot.matching import match_label, match_score, title_keywords
from price_bot.models import ComparisonResult, MatchedListing, Platform, ProductListing
from price_bot.platforms.ozon import OzonClient
from price_bot.platforms.wildberries import FetchError, WildberriesClient
from price_bot.platforms.yandex_market import YandexMarketClient
from price_bot.url_parser import fallback_search_query, parse_product_url

_CLIENTS = {
    Platform.OZON: OzonClient(),
    Platform.WILDBERRIES: WildberriesClient(),
    Platform.YANDEX_MARKET: YandexMarketClient(),
}


def _client_for(platform: Platform):
    return _CLIENTS[platform]


def compare_url(url: str, *, demo: bool | None = None) -> ComparisonResult:
    use_demo = DEMO_MODE if demo is None else demo
    if use_demo:
        return demo_comparison_for_url(url)

    parsed = parse_product_url(url)
    errors: list[str] = []
    source_client = _client_for(parsed.platform)

    try:
        source = source_client.fetch_product(parsed.product_id, parsed.canonical_url)
        source.is_source = True
        query = title_keywords(source.title)
    except FetchError as exc:
        source = ProductListing(
            platform=parsed.platform,
            product_id=parsed.product_id,
            title="Исходная карточка недоступна (цена и название могут отсутствовать)",
            price_rub=None,
            url=parsed.canonical_url,
            is_source=True,
        )
        errors.append(str(exc))
        query = fallback_search_query(url, parsed.product_id)
        if not query.strip():
            errors.append(
                "Сопоставление на других площадках не выполнялось: не удалось получить "
                "название товара для поиска."
            )
            return ComparisonResult(source=source, matches=[], errors=errors)
        if query == parsed.product_id:
            errors.append(
                "Поиск на других площадках выполнен по артикулу из ссылки — совпадения могут быть неточными."
            )
        else:
            errors.append(
                "Исходная карточка недоступна — поиск на других площадках по тексту из URL ссылки."
            )
    matches: list[MatchedListing] = []

    for platform in Platform:
        if platform == parsed.platform:
            continue
        client = _client_for(platform)
        try:
            candidates = client.search_products(query, limit=3)
        except FetchError as exc:
            errors.append(str(exc))
            continue
        if not candidates:
            errors.append(f"{platform.label_ru}: поиск не вернул результатов.")
            continue

        best = max(candidates, key=lambda c: match_score(source.title, c.title))
        score = match_score(source.title, best.title)
        # Enrich price if search hit lacks price
        if best.price_rub is None:
            try:
                detailed = client.fetch_product(best.product_id, best.url)
                best.title = detailed.title or best.title
                best.price_rub = detailed.price_rub
            except FetchError as exc:
                errors.append(f"{platform.label_ru}: {exc}")

        matches.append(
            MatchedListing(
                platform=best.platform,
                product_id=best.product_id,
                title=best.title,
                price_rub=best.price_rub,
                url=best.url,
                barcode=best.barcode,
                match_score=score,
                match_label=match_label(score),
            )
        )

    return ComparisonResult(source=source, matches=matches, errors=errors)
