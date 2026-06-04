"""CLI entry point for building the taxonomy reference database."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import TextIO
import urllib.request

from taxonomy_resolver.build import build_taxonomy_database

DEFAULT_TAXDUMP_URL = "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the database bootstrap command."""

    parser = argparse.ArgumentParser(
        description="Build the taxonomy SQLite database from an NCBI taxdump archive."
    )
    parser.add_argument("--dump", required=True, help="Path to NCBI taxdump.tar.gz")
    parser.add_argument("--db", required=True, help="Output SQLite database path")
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download the NCBI taxdump archive to --dump before building the database",
    )
    parser.add_argument(
        "--download-url",
        default=DEFAULT_TAXDUMP_URL,
        help="Source URL used when --download is enabled",
    )
    parser.add_argument(
        "--report-json",
        help="Optional path for writing the build summary as JSON",
    )
    return parser.parse_args()


def configure_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the `build-db` subcommand for the unified CLI."""

    parser = subparsers.add_parser("build-db", help="Build the taxonomy SQLite database")
    parser.add_argument("--dump", required=True, help="Path to NCBI taxdump.tar.gz")
    parser.add_argument("--db", required=True, help="Output SQLite database path")
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download the NCBI taxdump archive to --dump before building the database",
    )
    parser.add_argument(
        "--download-url",
        default=DEFAULT_TAXDUMP_URL,
        help="Source URL used when --download is enabled",
    )
    parser.add_argument("--report-json", help="Optional path for writing the build report as JSON")
    parser.set_defaults(func=run)


def _format_size(num_bytes: int) -> str:
    """Format byte counts into a compact human-readable string."""

    units = ["B", "KB", "MB", "GB"]
    size = float(num_bytes)
    unit = units[0]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            break
        size /= 1024
    return f"{size:.1f} {unit}"


def _render_progress(downloaded: int, total: int | None) -> str:
    """Render one progress line for the download step."""

    downloaded_text = _format_size(downloaded)
    if total and total > 0:
        percent = downloaded / total * 100
        total_text = _format_size(total)
        return f"\rDownloading taxdump: {percent:5.1f}% ({downloaded_text} / {total_text})"
    return f"\rDownloading taxdump: {_format_size(downloaded)}"


class BuildProgressPrinter:
    """Render build stage updates as friendly CLI progress lines."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream if stream is not None else sys.stderr
        self._active_stage: str | None = None

    def __call__(
        self,
        stage: str,
        message: str,
        current: int | None,
        total: int | None,
        final: bool,
    ) -> None:
        """Print one build progress event."""

        if self._active_stage is not None and stage != self._active_stage:
            print(file=self.stream, flush=True)
            self._active_stage = None

        line = self._render_line(message, current, total)
        if current is not None and not final:
            self._active_stage = stage
            print(f"\r{line}", end="", file=self.stream, flush=True)
            return

        if self._active_stage is not None:
            print(file=self.stream, flush=True)
            self._active_stage = None
        print(line, file=self.stream, flush=True)

    def finish(self) -> None:
        """Terminate any in-place progress line cleanly."""

        if self._active_stage is not None:
            print(file=self.stream, flush=True)
            self._active_stage = None

    def _render_line(self, message: str, current: int | None, total: int | None) -> str:
        """Render one build progress line."""

        if current is None:
            return message
        if total is not None and total > 0:
            percent = current / total * 100
            return f"{message}: {percent:5.1f}% ({current:,} / {total:,} rows)"
        return f"{message}: {current:,} rows"


def download_taxdump(
    url: str,
    destination: Path,
    *,
    progress_stream: TextIO | None = None,
    chunk_size: int = 1024 * 1024,
) -> None:
    """Download the NCBI taxdump archive to a local path.

    The builder still operates on a local archive file. This helper simply adds
    an optional one-step fetch phase before the normal local build path.
    """

    stream = progress_stream if progress_stream is not None else sys.stderr
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, destination.open("wb") as handle:
        total_bytes_header = response.headers.get("Content-Length")
        total_bytes = int(total_bytes_header) if total_bytes_header else None
        downloaded_bytes = 0

        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            handle.write(chunk)
            downloaded_bytes += len(chunk)
            print(
                _render_progress(downloaded_bytes, total_bytes),
                end="",
                file=stream,
                flush=True,
            )

    if stream is not None:
        final_suffix = (
            f" complete: {_format_size(downloaded_bytes)} downloaded"
            if total_bytes is None
            else " complete"
        )
        print(final_suffix, file=stream, flush=True)


def run(args: argparse.Namespace) -> None:
    """Build the taxonomy reference database from parsed CLI arguments."""

    dump_path = Path(args.dump)
    progress_printer = BuildProgressPrinter()
    if args.download:
        print(f"Downloading NCBI taxdump to {dump_path}")
        download_taxdump(args.download_url, dump_path)

    summary = build_taxonomy_database(
        dump_path,
        Path(args.db),
        progress_callback=progress_printer,
    )
    progress_printer.finish()

    if args.report_json:
        report_path = Path(args.report_json)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")

    print(f"Built taxonomy database at {summary.db_path}")
    print(f"Taxonomy build version: {summary.taxonomy_build_version}")
    print(f"Taxa: {summary.taxa_count}")
    print(f"Names: {summary.name_count}")
    print(f"Scientific names: {summary.scientific_name_count}")
    print(f"Synonyms/non-scientific names: {summary.synonym_count}")
    print(f"Lineage cache rows: {summary.lineage_cache_count}")
    print(f"Validation checks: {json.dumps(summary.validation_checks, sort_keys=True)}")


def main() -> None:
    """Run the legacy standalone build command."""

    run(parse_args())


if __name__ == "__main__":
    main()
