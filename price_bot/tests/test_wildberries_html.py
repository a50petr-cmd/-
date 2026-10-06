from price_bot.compare import compare_url
from price_bot.platforms.wildberries import _parse_product_html


def test_parse_next_data_product():
    html = """
    <html><body>
    <script id="__NEXT_DATA__" type="application/json">
    {"props":{"pageProps":{"product":{"id":177900896,"name":"Test Buds","salePriceU":899000}}}}
    </script></body></html>
    """
    listing = _parse_product_html(html, 177900896, "https://www.wildberries.ru/catalog/177900896/detail.aspx")
    assert listing is not None
    assert listing.title == "Test Buds"
    assert listing.price_rub == 8990


def test_compare_handles_fetch_error(monkeypatch):
    from price_bot.platforms import wildberries

    def fail_fetch(self, product_id, url):
        raise wildberries.FetchError("Wildberries: тестовая ошибка")

    monkeypatch.setattr(wildberries.WildberriesClient, "fetch_product", fail_fetch)
    result = compare_url("https://www.wildberries.ru/catalog/177900896/detail.aspx")
    assert result.errors
    assert "Wildberries" in result.errors[0]
