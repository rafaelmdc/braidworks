"""ensure_pageviews_db — acquiring the local Wikipedia pageviews DB (wikipedia_weaver).

The generic mechanics — consent gate, streamed download, cross-process build lock,
disk precheck, atomic publish — live in ``braidworks.core.localdb``. This module
supplies only the pageviews specifics: the source (a monthly Wikimedia
``pageview_complete`` dump), what makes a built DB valid, and the dump→SQLite build.

Why a dump and not the REST API? The api backend is per-article (one HTTP call per
title) — fine for a few thousand names, hopeless for the 1.25 M-title scopes
(Arthropoda) the fame ranking must cover. One monthly dump is a single streamed pass
that builds a complete ``title -> views`` table once, then every lookup is local.

Dump format (``/other/pageview_complete/monthly/YYYY/YYYY-MM/pageviews-YYYYMM-user.bz2``):
one space-separated line per (wiki, article, access-method):

    en.wikipedia Brown_bear 4623963 desktop 84187 J1K2…

The trailing field is an hourly-distribution code; the field *before* it is the
month's view total. We sum every English-Wikipedia access method (desktop + mobile)
per article title (titles are underscored, exactly as ``wikipedia.title`` emits them).
"""

from __future__ import annotations

import bz2
import logging
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Iterable

from braidworks.core.localdb import default_db_path as _core_default_db_path
from braidworks.core.localdb import download as _download
from braidworks.core.localdb import ensure_local_db

logger = logging.getLogger("wikipedia_weaver.setup")

# Monthly "user" (human, bot-filtered) pageviews, the agent split we want for fame.
DUMP_URL_TEMPLATE = (
    "https://dumps.wikimedia.org/other/pageview_complete/monthly/"
    "{year}/{year}-{month:02d}/pageviews-{year}{month:02d}-user.bz2"
)
# English Wikipedia across access methods — summed into one popularity figure.
ENWIKI_DOMAINS = frozenset({"en.wikipedia", "en.m.wikipedia", "en.zero.wikipedia"})

_NAMESPACE = "wikipedia"
_DB_FILENAME = "wikipedia_pageviews.sqlite"
# A ~3 GB bz2 download streams through; the built enwiki-only DB is ~0.4 GB. Keep headroom.
_MIN_FREE_BYTES = 8 * 1024**3
_UPSERT_BATCH = 50_000


def default_db_path() -> Path:
    """Per-user default DB path (``BRAIDWORKS_DATA_DIR`` overrides the cache dir)."""
    return _core_default_db_path(_NAMESPACE, _DB_FILENAME)


def db_is_valid(path: Path) -> bool:
    """Return whether ``path`` is a readable, built pageviews DB (stamped + populated)."""
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        row = con.execute("SELECT value FROM metadata WHERE key='dump_month'").fetchone()
        if not row or not row[0]:
            return False
        return con.execute("SELECT 1 FROM pageviews LIMIT 1").fetchone() is not None
    except sqlite3.Error:
        return False
    finally:
        con.close()


def _parse_lines(lines: Iterable[str]) -> Iterable[tuple[str, int]]:
    """Yield (article_title, views) for English-Wikipedia rows of a pageview_complete dump."""
    for line in lines:
        parts = line.split(" ")
        if len(parts) < 5 or parts[0] not in ENWIKI_DOMAINS:
            continue
        title = parts[1]
        try:
            views = int(parts[-2])  # last field is the hourly-distribution code
        except ValueError:
            continue
        if title and views:
            yield title, views


def build_pageviews_db(tmp_db: Path, *, source: IO[bytes] | Iterable[str], month: str) -> None:
    """Build the pageviews SQLite at ``tmp_db`` from a dump stream.

    ``source`` is either a binary bz2 file object (decompressed here) or an already
    decoded iterable of text lines (tests pass the latter). Views for the same title
    across access methods are summed via UPSERT in batched transactions so peak memory
    stays flat regardless of dump size.
    """
    # A binary file object is a bz2 dump to decompress+decode; tests pass text lines.
    if hasattr(source, "read"):
        text: Iterable[str] = bz2.open(source, mode="rt", encoding="utf-8", errors="replace")
    else:
        text = source

    con = sqlite3.connect(tmp_db)
    try:
        con.execute("PRAGMA journal_mode=OFF")
        con.execute("PRAGMA synchronous=OFF")
        con.execute("CREATE TABLE pageviews (title TEXT PRIMARY KEY, views INTEGER NOT NULL)")
        con.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")

        batch: list[tuple[str, int]] = []
        n = 0
        for title, views in _parse_lines(text):
            batch.append((title, views))
            if len(batch) >= _UPSERT_BATCH:
                _flush(con, batch)
                n += len(batch)
                batch.clear()
        if batch:
            _flush(con, batch)
            n += len(batch)

        con.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES ('dump_month', ?)", (month,)
        )
        con.commit()
        logger.info("built pageviews DB: %s rows from dump %s", n, month)
    finally:
        con.close()


def _flush(con: sqlite3.Connection, batch: list[tuple[str, int]]) -> None:
    con.executemany(
        "INSERT INTO pageviews(title, views) VALUES (?, ?) "
        "ON CONFLICT(title) DO UPDATE SET views = views + excluded.views",
        batch,
    )


def ensure_pageviews_db(
    db_path: str | Path | None,
    *,
    year: int,
    month: int,
    dump_path: str | Path | None = None,
    auto: bool = False,
    refresh: bool = False,
) -> Path:
    """Resolve (and if needed build) the local pageviews DB for a given month.

    ``dump_path`` uses an already-downloaded ``pageviews-YYYYMM-user.bz2`` instead of
    fetching it; otherwise the monthly dump is downloaded from Wikimedia (under the
    consent gate). The heavy build happens here, never inside a lookup.
    """
    target = Path(db_path) if db_path is not None else default_db_path()
    stamp = f"{year}{month:02d}"

    def build(tmp_db: Path) -> None:
        if dump_path is not None:
            with open(dump_path, "rb") as fh:
                build_pageviews_db(tmp_db, source=fh, month=stamp)
            return
        url = DUMP_URL_TEMPLATE.format(year=year, month=month)
        with tempfile_named(tmp_db.parent, ".bz2") as raw:
            _download(url, raw)
            with open(raw, "rb") as fh:
                build_pageviews_db(tmp_db, source=fh, month=stamp)

    return ensure_local_db(
        target,
        is_valid=db_is_valid,
        build=build,
        consent_message=(
            "The local Wikipedia pageviews backend needs a SQLite DB that is not present "
            f"yet.\n  source: {DUMP_URL_TEMPLATE.format(year=year, month=month)} (~3 GB)\n"
            "  builds: ~0.4 GB SQLite\n"
            f"  target: {target}\n"
            "Re-run with auto-download consent (auto_setup=True or BRAIDWORKS_AUTO_DOWNLOAD=1), "
            "or pass dump_path= to build from an already-downloaded dump."
        ),
        auto=auto,
        refresh=refresh,
        min_free_bytes=_MIN_FREE_BYTES,
    )


@contextmanager
def tempfile_named(directory: Path, suffix: str):
    """A named temp file on the same filesystem as the build, cleaned up after use."""
    fd, name = tempfile.mkstemp(dir=directory, suffix=suffix)
    os.close(fd)
    path = Path(name)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)
