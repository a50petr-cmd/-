from egrocery.telegram_util import parse_bot_command


def test_parse_search_with_bot_suffix() -> None:
    cmd, args = parse_bot_command("/search@MyEgroceryBot молоко 1.5%")
    assert cmd == "/search"
    assert args == "молоко 1.5%"


def test_parse_address_inline() -> None:
    cmd, args = parse_bot_command("/address Электросталь, Ялагина 13")
    assert cmd == "/address"
    assert "Ялагина" in args


def test_plain_text_not_command() -> None:
    cmd, args = parse_bot_command("Электросталь, Ялагина 13")
    assert cmd is None
    assert args == "Электросталь, Ялагина 13"
