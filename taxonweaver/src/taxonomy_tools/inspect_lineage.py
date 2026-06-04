"""CLI command for printing cached lineage for one taxid."""

from __future__ import annotations

import argparse

from .common import build_service, print_json


def parse_args() -> argparse.Namespace:
    """Parse arguments for the standalone `inspect-lineage` command."""

    parser = argparse.ArgumentParser(description="Inspect cached lineage for a taxid.")
    parser.add_argument("--db", required=True, help="Path to taxonomy SQLite database")
    parser.add_argument("--taxid", type=int, required=True, help="Taxid to inspect")
    return parser.parse_args()


def configure_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the `inspect-lineage` subcommand."""

    parser = subparsers.add_parser("inspect-lineage", help="Inspect cached lineage for a taxid")
    parser.add_argument("--db", required=True, help="Path to taxonomy SQLite database")
    parser.add_argument("--taxid", type=int, required=True, help="Taxid to inspect")
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    """Print lineage information for one taxid."""

    service = build_service(args)
    print_json({"taxid": args.taxid, "lineage": service.get_lineage(args.taxid)})


def main() -> None:
    """Run the standalone `inspect-lineage` command."""

    run(parse_args())


if __name__ == "__main__":
    main()
