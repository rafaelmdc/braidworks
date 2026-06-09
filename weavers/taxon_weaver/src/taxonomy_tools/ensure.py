"""CLI `ensure` subcommand: set up the local taxonomy DB (prompt + progress).

This is the recommended one-time path. With no flags it detects a missing DB,
announces what it will do (source, sizes, target), prompts for confirmation, and
shows download/build progress. ``--yes`` (or ``BRAIDWORKS_AUTO_DOWNLOAD``) skips
the prompt for non-interactive use; ``--refresh`` rebuilds an existing DB.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from taxon_weaver.setup import (
    DEFAULT_TAXDUMP_URL,
    auto_consented,
    check_for_update,
    db_is_valid,
    default_db_path,
    ensure_taxonomy_db,
)

from .build_ncbi_taxonomy import BuildProgressPrinter


def configure_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the `ensure` subcommand for the unified CLI."""

    parser = subparsers.add_parser(
        "ensure", help="Set up the local taxonomy database (download + build)"
    )
    parser.add_argument(
        "--db", help="Target SQLite path (default: per-user cache / BRAIDWORKS_DATA_DIR)"
    )
    parser.add_argument(
        "--refresh", action="store_true", help="Rebuild even if a valid DB already exists"
    )
    parser.add_argument(
        "--yes", "-y", action="store_true", help="Proceed without the confirmation prompt"
    )
    parser.add_argument("--url", default=DEFAULT_TAXDUMP_URL, help="Source taxdump URL")
    parser.set_defaults(func=run)


def _announce(target: Path) -> None:
    """Print what the build will do before asking for or assuming consent."""

    print(
        "Setting up the local taxonomy database:\n"
        "  source: NCBI taxdump.tar.gz (~70 MB download)\n"
        "  builds: ~1.2 GB SQLite, ~1 minute\n"
        f"  target: {target}",
        file=sys.stderr,
    )


def _confirm() -> bool:
    """Ask the user to confirm the build; default is No, EOF counts as No."""

    try:
        reply = input("Build it now? [y/N] ").strip().lower()
    except EOFError:
        return False
    return reply in {"y", "yes"}


def run(args: argparse.Namespace) -> None:
    """Ensure the local taxonomy DB exists, prompting and showing progress."""

    target = Path(args.db) if args.db else default_db_path()
    if db_is_valid(target) and not args.refresh:
        print(f"Taxonomy DB already present: {target}")
        status = check_for_update(target, url=args.url)
        if status is True:
            print("A newer NCBI taxonomy release is available. "
                  "Rebuild with: taxon-weaver ensure --refresh")
        elif status is False:
            print("It is current with the latest NCBI release.")
        return

    _announce(target)
    consented = args.yes or auto_consented(False)
    if not consented and sys.stdin.isatty() and sys.stdout.isatty():
        consented = _confirm()
    if not consented:
        print(
            "Aborted: setup not confirmed. Re-run with --yes or set BRAIDWORKS_AUTO_DOWNLOAD=1.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    printer = BuildProgressPrinter()
    ensure_taxonomy_db(
        target, auto=True, refresh=args.refresh, url=args.url, progress=printer
    )
    printer.finish()
    print(f"Taxonomy DB ready: {target}")


def main() -> None:
    """Run the standalone `ensure` command."""

    parser = argparse.ArgumentParser(description="Set up the local taxonomy database.")
    configure_parser(parser.add_subparsers(dest="command", required=True))
    run(parser.parse_args(["ensure", *sys.argv[1:]]))


if __name__ == "__main__":
    main()
