"""CLI command for persisting reviewed decisions from JSON input."""

from __future__ import annotations

import argparse
from pathlib import Path

from .common import build_service, parse_decisions, print_json, read_json


def parse_args() -> argparse.Namespace:
    """Parse arguments for the standalone `apply-decisions` command."""

    parser = argparse.ArgumentParser(description="Persist reviewed decisions from JSON.")
    parser.add_argument("--db", required=True, help="Path to taxonomy SQLite database")
    parser.add_argument("--cache-db", help="Optional separate reviewed-mapping SQLite database")
    parser.add_argument("--input", required=True, help="Input JSON file path")
    return parser.parse_args()


def configure_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the `apply-decisions` subcommand."""

    parser = subparsers.add_parser("apply-decisions", help="Persist reviewed decisions from JSON")
    parser.add_argument("--db", required=True, help="Path to taxonomy SQLite database")
    parser.add_argument("--cache-db", help="Optional separate reviewed-mapping SQLite database")
    parser.add_argument("--input", required=True, help="Input JSON file path")
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    """Persist reviewed decisions from JSON input."""

    service = build_service(args)
    payload = read_json(Path(args.input))
    decisions = parse_decisions(payload)
    for decision in decisions:
        service.record_decision(decision)

    print_json(
        {
            "applied_count": len(decisions),
            "taxonomy_db": str(args.db),
            "cache_db": str(args.cache_db) if args.cache_db else str(args.db),
        }
    )


def main() -> None:
    """Run the standalone `apply-decisions` command."""

    run(parse_args())


if __name__ == "__main__":
    main()
