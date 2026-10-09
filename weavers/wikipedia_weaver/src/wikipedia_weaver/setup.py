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
import hashlib
import json
import logging
import os
import re
import sqlite3
import tempfile
import uuid
from collections.abc import Iterable
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import IO

from braidworks.core import BackendConfigurationError
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
        meta = dict(con.execute("SELECT key, value FROM metadata"))
        _validate_month(meta.get("dump_month", ""))
        if meta.get("schema_version") != "2" or not re.fullmatch(
            r"[0-9a-f]{64}", meta.get("source_sha256", "")
        ):
            return False
        scope = json.loads(meta["measurement"])
        coverage = json.loads(meta["parser_coverage"])
        if not isinstance(coverage, dict):
            return False
        if scope != {
            "project": "en.wikipedia",
            "access": "all-access",
            "agent": "user",
            "granularity": "monthly",
            "month": meta["dump_month"],
        } or not isinstance(coverage.get("complete"), bool):
            return False
        if con.execute("SELECT 1 FROM pageviews WHERE views < 0 LIMIT 1").fetchone():
            return False
        return con.execute("SELECT 1 FROM pageviews LIMIT 1").fetchone() is not None
    except (sqlite3.Error, ValueError, KeyError, TypeError):
        return False
    finally:
        con.close()


def _parse_lines(lines: Iterable[str], coverage: dict | None = None) -> Iterable[tuple[str, int]]:
    """Validate relevant rows; malformed counts are diagnosed, never added."""
    stats = coverage if coverage is not None else {}
    stats.update(total_rows=0, irrelevant_rows=0, valid_rows=0, invalid_rows=0)
    for line in lines:
        stats["total_rows"] += 1
        parts = line.split()
        if parts and parts[0] not in ENWIKI_DOMAINS:
            stats["irrelevant_rows"] += 1
            continue
        try:
            if (
                len(parts) != 6
                or not parts[1]
                or parts[3] not in {"desktop", "mobile-web", "mobile-app"}
            ):
                raise ValueError("malformed English pageview row")
            views = int(parts[-2])
            if views < 0:
                raise ValueError("negative view count")
        except (ValueError, IndexError):
            stats["invalid_rows"] += 1
            continue
        stats["valid_rows"] += 1
        yield parts[1], views
    stats["complete"] = stats["invalid_rows"] == 0


class _HashingReader:
    def __init__(self, source, digest):
        self.source = source
        self.digest = digest

    def read(self, size=-1):
        data = self.source.read(size)
        self.digest.update(data)
        return data

    def __getattr__(self, name):
        return getattr(self.source, name)


def _validate_month(month: str) -> None:
    if not re.fullmatch(r"\d{6}", month) or not 1 <= int(month[4:]) <= 12 or int(month[:4]) < 1:
        raise ValueError("dump month must be YYYYMM with a valid month")


def build_pageviews_db(
    tmp_db: Path, *, source: IO[bytes] | Iterable[str], month: str, source_url: str | None = None
) -> None:
    """Build the pageviews SQLite at ``tmp_db`` from a dump stream.

    ``source`` is either a binary bz2 file object (decompressed here) or an already
    decoded iterable of text lines (tests pass the latter). Views for the same title
    across access methods are summed via UPSERT in batched transactions so peak memory
    stays flat regardless of dump size.
    """
    _validate_month(month)
    digest = hashlib.sha256()
    coverage: dict = {}
    binary = hasattr(source, "read")
    with ExitStack() as stack:
        # A binary file object is a bz2 dump to decompress+decode; tests pass text lines.
        if hasattr(source, "read"):
            text: Iterable[str] = stack.enter_context(
                bz2.open(
                    _HashingReader(source, digest), mode="rt", encoding="utf-8", errors="strict"
                )
            )
        else:

            def hashed_lines():
                for line in source:
                    encoded = line.encode("utf-8")
                    digest.update(len(encoded).to_bytes(8, "big"))
                    digest.update(encoded)
                    yield line

            text = hashed_lines()

        con = sqlite3.connect(tmp_db)
        try:
            con.execute("PRAGMA journal_mode=OFF")
            con.execute("PRAGMA synchronous=OFF")
            con.execute("CREATE TABLE pageviews (title TEXT PRIMARY KEY, views INTEGER NOT NULL)")
            con.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")

            batch: list[tuple[str, int]] = []
            n = 0
            for title, views in _parse_lines(text, coverage):
                batch.append((title, views))
                if len(batch) >= _UPSERT_BATCH:
                    _flush(con, batch)
                    n += len(batch)
                    batch.clear()
            if batch:
                _flush(con, batch)
                n += len(batch)

            con.executemany(
                "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
                [
                    ("schema_version", "2"),
                    ("build_id", uuid.uuid4().hex),
                    ("source_sha256", digest.hexdigest()),
                    ("source_kind", "compressed-bz2" if binary else "decoded-lines"),
                    ("source_url", source_url or "caller-supplied"),
                    (
                        "measurement",
                        json.dumps(
                            {
                                "project": "en.wikipedia",
                                "access": "all-access",
                                "agent": "user",
                                "granularity": "monthly",
                                "month": month,
                            },
                            sort_keys=True,
                        ),
                    ),
                    ("parser_coverage", json.dumps(coverage, sort_keys=True)),
                ],
            )
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
    if (
        isinstance(year, bool)
        or isinstance(month, bool)
        or not isinstance(year, int)
        or not isinstance(month, int)
    ):
        raise TypeError("year and month must be integers")
    stamp = f"{year:04d}{month:02d}"
    _validate_month(stamp)
    if db_is_valid(target) and not refresh:
        with sqlite3.connect(target) as con:
            actual = con.execute("SELECT value FROM metadata WHERE key='dump_month'").fetchone()[0]
        if actual != stamp:
            raise BackendConfigurationError(
                f"pageviews DB month={actual}, requested={stamp}; choose another db_path or refresh=True"
            )
    if dump_path is not None:
        match = re.search(r"pageviews-(\d{6})-", Path(dump_path).name)
        if match and match[1] != stamp:
            raise BackendConfigurationError(f"dump filename month={match[1]}, requested={stamp}")

    def build(tmp_db: Path) -> None:
        if dump_path is not None:
            with open(dump_path, "rb") as fh:
                build_pageviews_db(
                    tmp_db, source=fh, month=stamp, source_url=str(Path(dump_path).absolute())
                )
            return
        url = DUMP_URL_TEMPLATE.format(year=year, month=month)
        with tempfile_named(tmp_db.parent, ".bz2") as raw:
            _download(url, raw)
            with open(raw, "rb") as fh:
                build_pageviews_db(tmp_db, source=fh, month=stamp, source_url=url)

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
