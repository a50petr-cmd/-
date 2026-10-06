import unittest

from price_bot.models import Platform
from price_bot.url_parser import parse_product_url


class UrlParserTests(unittest.TestCase):
    def test_ozon(self):
        p = parse_product_url("https://www.ozon.ru/product/naushniki-123456789/")
        self.assertEqual(p.platform, Platform.OZON)
        self.assertEqual(p.product_id, "123456789")

    def test_wildberries(self):
        p = parse_product_url("https://www.wildberries.ru/catalog/177900896/detail.aspx")
        self.assertEqual(p.platform, Platform.WILDBERRIES)
        self.assertEqual(p.product_id, "177900896")

    def test_yandex(self):
        p = parse_product_url("https://market.yandex.ru/product--buds/43567890")
        self.assertEqual(p.platform, Platform.YANDEX_MARKET)
        self.assertEqual(p.product_id, "43567890")


if __name__ == "__main__":
    unittest.main()
