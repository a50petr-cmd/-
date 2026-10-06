from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Platform(str, Enum):
    OZON = "ozon"
    WILDBERRIES = "wildberries"
    YANDEX_MARKET = "yandex_market"

    @property
    def label_ru(self) -> str:
        return {
            Platform.OZON: "Ozon",
            Platform.WILDBERRIES: "Wildberries",
            Platform.YANDEX_MARKET: "Яндекс Маркет",
        }[self]


@dataclass
class ProductListing:
    platform: Platform
    product_id: str
    title: str
    price_rub: Optional[int]
    url: str
    barcode: Optional[str] = None
    is_source: bool = False


@dataclass
class MatchedListing(ProductListing):
    match_score: float = 0.0
    match_label: str = "похожее"


@dataclass
class ComparisonResult:
    source: ProductListing
    matches: list[MatchedListing] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def all_listings(self) -> list[ProductListing | MatchedListing]:
        items: list[ProductListing | MatchedListing] = list(self.matches)
        items.append(self.source)
        return items

    def cheapest(self) -> Optional[ProductListing | MatchedListing]:
        priced = [x for x in self.all_listings() if x.price_rub is not None]
        if not priced:
            return None
        return min(priced, key=lambda x: x.price_rub or 0)
