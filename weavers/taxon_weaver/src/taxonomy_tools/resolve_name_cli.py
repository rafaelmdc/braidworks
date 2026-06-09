"""Legacy wrapper for the standalone resolve-name command."""

from __future__ import annotations

import argparse

from .resolve_name import run


def parse_args() -> argparse.Namespace:
    """Parse arguments using the unified CLI command shape.

    This wrapper preserves the existing module entry point while delegating the
    real work to the unified `resolve-name` subcommand.
    """

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


def main() -> None:
    """Run the legacy standalone resolve-name command."""

    args = parse_args()
    run(args)


if __name__ == "__main__":
    main()
