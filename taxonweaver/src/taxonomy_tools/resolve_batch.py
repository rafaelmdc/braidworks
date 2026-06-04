"""CLI command for resolving batch JSON input."""

from __future__ import annotations

import argparse
from pathlib import Path

from .common import build_service, parse_batch_request, print_json, read_json, write_json


def parse_args() -> argparse.Namespace:
    """Parse arguments for the standalone `resolve-batch` command."""

    parser = argparse.ArgumentParser(description="Resolve batch JSON input.")
    parser.add_argument("--db", required=True, help="Path to taxonomy SQLite database")
    parser.add_argument("--cache-db", help="Optional separate reviewed-mapping SQLite database")
    parser.add_argument("--input", required=True, help="Input JSON file path")
    parser.add_argument("--output", help="Optional output JSON file path")
    return parser.parse_args()


def configure_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the `resolve-batch` subcommand."""

    parser = subparsers.add_parser("resolve-batch", help="Resolve batch JSON input")
    parser.add_argument("--db", required=True, help="Path to taxonomy SQLite database")
    parser.add_argument("--cache-db", help="Optional separate reviewed-mapping SQLite database")
    parser.add_argument("--input", required=True, help="Input JSON file path")
    parser.add_argument("--output", help="Optional output JSON file path")
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    """Resolve a batch of organism names from JSON input."""

    service = build_service(args)
    payload = read_json(Path(args.input))
    batch_request = parse_batch_request(payload)
    result = service.resolve_batch(batch_request).to_dict()
    if args.output:
        write_json(Path(args.output), result)
        return
    print_json(result)


def main() -> None:
    """Run the standalone `resolve-batch` command."""

    run(parse_args())


if __name__ == "__main__":
    main()
