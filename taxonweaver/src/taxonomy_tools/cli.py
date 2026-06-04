"""Unified CLI entry point that wires together per-command modules."""

from __future__ import annotations

import argparse
from . import apply_decisions, build_info, build_ncbi_taxonomy, inspect_lineage, resolve_batch, resolve_name


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level parser and register command modules."""

    parser = argparse.ArgumentParser(description="Unified CLI for the taxonomy resolver.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_ncbi_taxonomy.configure_parser(subparsers)
    resolve_name.configure_parser(subparsers)
    resolve_batch.configure_parser(subparsers)
    inspect_lineage.configure_parser(subparsers)
    apply_decisions.configure_parser(subparsers)
    build_info.configure_parser(subparsers)

    return parser


def main() -> None:
    """Run the unified CLI."""

    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
