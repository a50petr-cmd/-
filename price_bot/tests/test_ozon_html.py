from price_bot.platforms.ozon import parse_product_html, parse_search_html


def test_parse_ld_json_product_price():
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@type":"Product","name":"Зимняя шина 205/55 R16","offers":{"@type":"Offer","price":"12490","priceCurrency":"RUB"}}
    </script>
    </head></html>
    """
    listing = parse_product_html(html, "2909664592", "https://www.ozon.ru/product/-2909664592/")
    assert listing is not None
    assert listing.title.startswith("Зимняя")
    assert listing.price_rub == 12490


def test_parse_embedded_price_regex():
    html = """
    <html><body><div data-state='{"price":"8990","title":"Test tire"}'></div></body></html>
    """
    listing = parse_product_html(html, "12345678", "https://www.ozon.ru/product/-12345678/")
    assert listing is not None
    assert listing.price_rub == 8990


def test_parse_search_html_links():
    html = """
    <a href="/product/slug-11111111/">A</a>
    <span>"/product/slug-22222222/"</span> "price":"15990"
    """
    hits = parse_search_html(html, limit=2)
    assert len(hits) == 2
    assert hits[0].product_id == "11111111"
    assert hits[1].product_id == "22222222"
    assert hits[1].price_rub == 15990
