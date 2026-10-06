from __future__ import annotations

import argparse
from pathlib import Path

from egrocery.config import get_basket_path, get_location_path
from egrocery.loaders import load_basket, load_location
from egrocery.table import format_basket_table


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="egrocery",
        description="E-grocery basket comparison scaffold (P0).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

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

    args = parser.parse_args(argv)
    if args.command == "basket":
        loc_path = get_location_path() if args.location is None else Path(args.location)
        basket_path = (
            get_basket_path() if args.basket is None else Path(args.basket)
        )
        location = load_location(loc_path)
        basket = load_basket(basket_path)
        print(format_basket_table(location, basket))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
