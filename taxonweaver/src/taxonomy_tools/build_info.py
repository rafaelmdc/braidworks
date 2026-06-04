"""CLI command for printing taxonomy build metadata."""

from __future__ import annotations

import argparse

from .common import build_service, print_json


def parse_args() -> argparse.Namespace:
    """Parse arguments for the standalone `build-info` command."""

    parser = argparse.ArgumentParser(description="Show taxonomy build metadata.")
    parser.add_argument("--db", required=True, help="Path to taxonomy SQLite database")
    return parser.parse_args()


def configure_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the `build-info` subcommand."""

    parser = subparsers.add_parser("build-info", help="Show taxonomy build metadata")
    parser.add_argument("--db", required=True, help="Path to taxonomy SQLite database")
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    """Print taxonomy build metadata from the SQLite database."""

    service = build_service(args)
    print_json(service.get_taxonomy_build_info())


def main() -> None:
    """Run the standalone `build-info` command."""

    run(parse_args())


if __name__ == "__main__":
    main()
