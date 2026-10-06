import unittest

from price_bot.matching import match_label, match_score, title_keywords


class MatchingTests(unittest.TestCase):
    def test_keywords_trim_noise(self):
        q = title_keywords("Samsung Galaxy Buds2 Pro — Graphite, купить")
        self.assertIn("samsung", q)
        self.assertIn("buds2", q)

    def test_same_product_high_score(self):
        a = "Samsung Galaxy Buds2 Pro Graphite"
        b = "Наушники Samsung Galaxy Buds 2 Pro graphite"
        self.assertGreater(match_score(a, b), 0.5)
        self.assertIn(match_label(match_score(a, b)), ("то же", "похожее"))


if __name__ == "__main__":
    unittest.main()
