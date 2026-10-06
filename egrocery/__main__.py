from __future__ import annotations

import argparse
from pathlib import Path

from egrocery.basket_service import build_basket_markdown
from egrocery.bot import main as bot_main
from egrocery.search_service import build_search_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="egrocery",
        description="E-grocery basket comparison scaffold (P0) + Telegram bot.",
    )
    sub = parser.add_subparsers(dest="command")

    basket_p = sub.add_parser(
        "basket",
        help="Print markdown table for store basket vs enabled services",
    )
    basket_p.add_argument(
        "--location",
        type=str,
        default=None,
        help="Override location YAML (default: JOB_AGENT_STORE/docs/e-grocery-location.yaml)",
    )
    basket_p.add_argument(
        "--basket",
        type=str,
        default=None,
        help="Override basket YAML (default: JOB_AGENT_STORE/docs/e-grocery-basket-starter.yaml)",
    )
    basket_p.add_argument(
        "--chat-id",
        type=int,
        default=None,
        help="Load saved delivery point for this Telegram chat_id from store",
    )
    basket_p.add_argument(
        "--lat",
        type=float,
        default=None,
        help="Override latitude (testing)",
    )
    basket_p.add_argument(
        "--lon",
        type=float,
        default=None,
        help="Override longitude (testing)",
    )

    search_p = sub.add_parser(
        "search",
        help='Find cheapest offers per service for a query (e.g. "молоко 1.5%")',
    )
    search_p.add_argument("query", type=str, help="Product search text")
    search_p.add_argument("--chat-id", type=int, default=None)
    search_p.add_argument("--lat", type=float, default=None)
    search_p.add_argument("--lon", type=float, default=None)
    search_p.add_argument(
        "--location",
        type=str,
        default=None,
        help="Override location YAML",
    )

    sub.add_parser("bot", help="Run Telegram bot (EGROCERY_BOT_TOKEN)")

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "basket":
        loc_path = Path(args.location) if args.location else None
        basket_path = Path(args.basket) if args.basket else None
        print(
            build_basket_markdown(
                location_path=loc_path,
                basket_path=basket_path,
                chat_id=args.chat_id,
                lat=args.lat,
                lon=args.lon,
            )
        )
        return 0
    if args.command == "search":
        loc_path = Path(args.location) if args.location else None
        print(
            build_search_markdown(
                args.query,
                chat_id=args.chat_id,
                lat=args.lat,
                lon=args.lon,
                location_path=loc_path,
            )
        )
        return 0
    if args.command == "bot":
        return bot_main()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
