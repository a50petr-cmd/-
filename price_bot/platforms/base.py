from __future__ import annotations

from abc import ABC, abstractmethod

from price_bot.models import Platform, ProductListing


class MarketplaceClient(ABC):
    platform: Platform

    @abstractmethod
    def fetch_product(self, product_id: str, url: str) -> ProductListing:
        ...

    @abstractmethod
    def search_products(self, query: str, limit: int = 3) -> list[ProductListing]:
        ...
