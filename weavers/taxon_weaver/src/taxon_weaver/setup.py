"""ensure_taxonomy_db — acquiring the local NCBI taxonomy DB (taxon_weaver-specific).

The generic mechanics — the consent gate, streamed download, MD5 integrity check,
disk precheck, cross-process build lock, and atomic publish — live in
``braidworks.core.localdb``. This module supplies only the taxonomy specifics: the
source URL, what makes a built DB *valid*, the build itself (taxdump → SQLite,
recording the source MD5), the actionable consent message, and the update check.

Interactive entry points (the ``ensure`` CLI and the factory on a TTY) obtain consent
by *prompting*, then call this with ``auto=True``. This function never prompts, so it
stays deterministic and easy to test.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from braidworks.core import BackendConfigurationError
from braidworks.core.localdb import auto_consented, default_db_path as _core_default_db_path
from braidworks.core.localdb import download as _download
from braidworks.core.localdb import ensure_local_db
from braidworks.core.localdb import fetch_remote_md5 as _fetch_remote_md5
from braidworks.core.localdb import md5_file as _md5_file
from taxonomy_resolver.build import ProgressCallback, build_taxonomy_database
from taxonomy_resolver.db import upsert_metadata

_SOURCE_MD5_KEY = "source_dump_md5"

logger = logging.getLogger("taxon_weaver.setup")

DEFAULT_TAXDUMP_URL = "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz"
_NAMESPACE = "taxonomy"
_DB_FILENAME = "ncbi_taxonomy.sqlite"
# A ~70 MB download + ~1.2 GB DB + temporary build headroom; require a safe margin.
_MIN_FREE_BYTES = 4 * 1024**3

# Re-export the generic consent helper so existing imports keep working.
__all__ = [
    "auto_consented",
    "check_for_update",
    "db_is_valid",
    "default_db_path",
    "ensure_taxonomy_db",
    "DEFAULT_TAXDUMP_URL",
]


def default_db_path() -> Path:
    """Per-user default DB path (``BRAIDWORKS_DATA_DIR`` overrides the cache dir)."""
    return _core_default_db_path(_NAMESPACE, _DB_FILENAME)


def db_is_valid(path: Path) -> bool:
    """Return whether ``path`` is a readable, built taxonomy DB (versioned + populated)."""
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        row = con.execute(
            "SELECT value FROM metadata WHERE key = 'taxonomy_build_version'"
        ).fetchone()
        if not row or not row[0]:
            return False
        return con.execute("SELECT 1 FROM taxa LIMIT 1").fetchone() is not None
    except sqlite3.Error:
        return False
    finally:
        con.close()


def _consent_message(db_path: Path) -> str:
    """Build the actionable error shown when a DB is missing and consent was not given."""
    return (
        f"taxonomy database not found at {db_path}.\n"
        "The local backend needs a SQLite taxonomy DB "
        "(~1.2 GB, built from a ~70 MB NCBI download, ~1 minute). To create it:\n"
        "  - run:  taxon-weaver ensure\n"
        "  - or call: build_ncbi_weaver(auto_setup=True)\n"
        "  - or set: BRAIDWORKS_AUTO_DOWNLOAD=1\n"
        "Or build it yourself and pass db_path=:\n"
        "  taxon-weaver build-db --download --dump <taxdump.tar.gz> --db <db.sqlite>"
    )


def _verify_download(archive: Path, url: str) -> str:
    """Verify the archive against NCBI's published MD5 (raise on mismatch); return its MD5."""
    actual = _md5_file(archive)
    expected = _fetch_remote_md5(url)
    if expected is not None and actual != expected:
        raise BackendConfigurationError(
            f"taxdump checksum mismatch: expected {expected}, got {actual} (download corrupt?)"
        )
    if expected is not None:
        logger.info("verified taxdump checksum (md5=%s)", actual)
    return actual


def _stored_source_md5(path: Path) -> str | None:
    """Read the source taxdump MD5 recorded when this DB was built, if any."""
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        row = con.execute("SELECT value FROM metadata WHERE key = ?", (_SOURCE_MD5_KEY,)).fetchone()
        return row[0] if row and row[0] else None
    except sqlite3.Error:
        return None
    finally:
        con.close()


def check_for_update(path: str | Path, *, url: str = DEFAULT_TAXDUMP_URL) -> bool | None:
    """Notify (never replace) whether a newer NCBI taxonomy release exists.

    Compares the digest of the taxdump this DB was built from against NCBI's current
    published MD5. Returns True if newer, False if current, None if undetermined
    (older DB or network error). Decision 3: notify, never auto-replace — the caller
    rebuilds with ``refresh=True``.
    """
    local = _stored_source_md5(Path(path))
    remote = _fetch_remote_md5(url)
    if local is None or remote is None:
        return None
    if local == remote:
        logger.info("local taxonomy DB is current with the latest NCBI release")
        return False
    logger.info("a newer NCBI taxonomy release is available; rebuild with refresh=True")
    return True


def _build_taxonomy_db(tmp_db: Path, *, url: str, progress: ProgressCallback | None) -> None:
    """Build callback for ``ensure_local_db``: download → verify → build → record MD5."""
    logger.info("acquiring NCBI taxonomy DB -> %s (source: %s)", tmp_db, url)
    archive = tmp_db.parent / "taxdump.tar.gz"
    _download(url, archive, progress=progress, label="Downloading taxdump")
    archive_md5 = _verify_download(archive, url)
    summary = build_taxonomy_database(archive, tmp_db, progress_callback=progress)
    if not all(summary.validation_checks.values()):
        raise BackendConfigurationError(
            f"built taxonomy DB failed validation: {summary.validation_checks}"
        )
    # Record the source digest so check_for_update() can later detect staleness.
    upsert_metadata(tmp_db, {_SOURCE_MD5_KEY: archive_md5})
    logger.info("taxonomy DB built: %s (build %s)", tmp_db, summary.taxonomy_build_version)


def ensure_taxonomy_db(
    path: str | Path | None = None,
    *,
    auto: bool = False,
    refresh: bool = False,
    url: str = DEFAULT_TAXDUMP_URL,
    progress: ProgressCallback | None = None,
) -> Path:
    """Ensure a valid local taxonomy DB exists, returning its path.

    Idempotent: a valid DB present (and ``refresh`` False) returns instantly.
    Otherwise acquisition requires consent (``auto=True`` or
    ``BRAIDWORKS_AUTO_DOWNLOAD``); without it an actionable error is raised. The
    generic orchestration (lock, disk precheck, atomic publish) lives in
    ``braidworks.core.localdb.ensure_local_db``.
    """
    db_path = Path(path) if path is not None else default_db_path()
    return ensure_local_db(
        db_path,
        is_valid=db_is_valid,
        build=lambda target: _build_taxonomy_db(target, url=url, progress=progress),
        consent_message=_consent_message(db_path),
        auto=auto,
        refresh=refresh,
        min_free_bytes=_MIN_FREE_BYTES,
    )
