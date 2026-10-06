from egrocery.offers import Offer, filter_offers_for_query, pick_cheapest_offer


def test_filter_milk_15_excludes_32() -> None:
    offers = [
        Offer(service="v", product_name="Молоко 3,2%, 1 л", price_rub=93.0),
        Offer(service="v", product_name="Молоко 1,5%, 1 л", price_rub=110.0),
    ]
    filtered, note = filter_offers_for_query(offers, "молоко 1.5%")
    assert len(filtered) == 1
    assert "1,5" in filtered[0].product_name
    assert note is None


def test_filter_falls_back_with_note() -> None:
    offers = [
        Offer(service="v", product_name="Молоко 3,2%, 1 л", price_rub=93.0),
    ]
    filtered, note = filter_offers_for_query(offers, "молоко 1.5%")
    assert filtered == offers
    assert note is not None
