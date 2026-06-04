"""CLI command for resolving one organism name."""

from __future__ import annotations

import argparse

from taxonomy_resolver.schemas import ResolveRequest

from .common import build_service, print_json


def parse_args() -> argparse.Namespace:
    """Parse arguments for the standalone `resolve-name` command."""

    parser = argparse.ArgumentParser(description="Resolve one organism name.")
    parser.add_argument("name", help="Organism name to resolve")
    parser.add_argument("--db", required=True, help="Path to taxonomy SQLite database")
    parser.add_argument("--cache-db", help="Optional separate reviewed-mapping SQLite database")
    parser.add_argument("--level", help="Optional curator-provided taxonomic level")
    parser.add_argument(
        "--no-fuzzy",
        action="store_true",
        help="Disable fuzzy fallback and return only deterministic/cache outcomes",
    )
    return parser.parse_args()


def configure_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the `resolve-name` subcommand."""

    parser = subparsers.add_parser("resolve-name", help="Resolve one organism name")
    parser.add_argument("name", help="Organism name to resolve")
    parser.add_argument("--db", required=True, help="Path to taxonomy SQLite database")
    parser.add_argument("--cache-db", help="Optional separate reviewed-mapping SQLite database")
    parser.add_argument("--level", help="Optional curator-provided taxonomic level")
    parser.add_argument(
        "--no-fuzzy",
        action="store_true",
        help="Disable fuzzy fallback and return only deterministic/cache outcomes",
    )
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    """Resolve one organism name and print the structured result."""

    service = build_service(args)
    result = service.resolve_name(
        ResolveRequest(
            original_name=args.name,
            provided_level=args.level,
            allow_fuzzy=not args.no_fuzzy,
        )
    )
    print_json(result.to_dict())


def main() -> None:
    """Run the standalone `resolve-name` command."""

    run(parse_args())


if __name__ == "__main__":
    main()
