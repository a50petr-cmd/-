from __future__ import annotations

import argparse
import sys

from price_bot.compare import compare_url
from price_bot.formatters import format_comparison_message
from price_bot.telegram_bot import run_bot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="price_bot",
        description="Compare prices across Ozon, Wildberries, and Yandex Market.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("bot", help="Run Telegram polling bot")

    compare_p = sub.add_parser("compare", help="Compare a single product URL (CLI)")
    compare_p.add_argument("url", help="Product URL")
    compare_p.add_argument(
        "--demo",
        action="store_true",
        help="Use built-in demo data (no marketplace HTTP)",
    )

    args = parser.parse_args(argv)
    if args.command == "bot" or args.command is None:
        run_bot()
        return 0
    if args.command == "compare":
        result = compare_url(args.url, demo=args.demo)
        print(format_comparison_message(result))
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
