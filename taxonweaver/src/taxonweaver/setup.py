"""ensure_taxonomy_db — single source of truth for acquiring the local taxonomy DB.

Domain-specific to ``taxonweaver`` (never ``braidworks-core``). It owns
default-path resolution, the opt-in consent gate, an integrity-checked download,
an atomically-published build, a cross-process lock, and a disk precheck.

Interactive entry points (the ``ensure`` CLI and the factory on a TTY) obtain
consent by *prompting*, then call this with ``auto=True``. This function itself
never prompts, so it stays deterministic and easy to test. Heavy work (a ~70 MB
download, a ~1-minute build, ~1.2 GB on disk) never fires unless someone has
consented via ``auto=True`` or the ``BRAIDWORKS_AUTO_DOWNLOAD`` env var.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import sqlite3
import tempfile
import time
import urllib.request
from pathlib import Path

from platformdirs import user_cache_dir

from braidworks.core import BackendConfigurationError
from taxonomy_resolver.build import ProgressCallback, build_taxonomy_database
from taxonomy_resolver.db import upsert_metadata

_SOURCE_MD5_KEY = "source_dump_md5"

logger = logging.getLogger("taxonweaver.setup")

DEFAULT_TAXDUMP_URL = "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz"
_ENV_DATA_DIR = "BRAIDWORKS_DATA_DIR"
_ENV_AUTO = "BRAIDWORKS_AUTO_DOWNLOAD"
_DB_FILENAME = "taxonomy.sqlite"
# A ~70 MB download + ~1.2 GB DB + temporary build headroom; require a safe margin.
_MIN_FREE_BYTES = 4 * 1024**3
# A lock older than this is assumed abandoned (a crashed build) and reclaimed.
_LOCK_STALE_SECONDS = 2 * 60 * 60
_LOCK_POLL_SECONDS = 1.0
_TRUTHY = {"1", "true", "yes", "on"}


def default_db_path() -> Path:
    """Resolve the per-user default DB path (``BRAIDWORKS_DATA_DIR`` overrides the cache dir)."""
    override = os.environ.get(_ENV_DATA_DIR)
    base = Path(override) if override else Path(user_cache_dir("braidworks"))
    return base / "taxonomy" / _DB_FILENAME


def auto_consented(auto: bool) -> bool:
    """Return whether heavy acquisition is consented to (explicit flag or env var)."""
    if auto:
        return True
    return os.environ.get(_ENV_AUTO, "").strip().lower() in _TRUTHY


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


def _md5_file(path: Path) -> str:
    """Compute the MD5 of a local file (NCBI publishes MD5 for taxdump.tar.gz)."""
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fetch_remote_md5(url: str) -> str | None:
    """Fetch and parse NCBI's published ``<url>.md5`` digest; None if unavailable."""
    try:
        with urllib.request.urlopen(f"{url}.md5") as response:
            text = response.read().decode("utf-8")
    except (OSError, ValueError) as exc:  # network/URL errors — integrity check is best-effort
        logger.warning("could not fetch checksum %s.md5 (%s); skipping integrity check", url, exc)
        return None
    parts = text.split()
    return parts[0].lower() if parts else None


def _download(
    url: str, destination: Path, *, progress: ProgressCallback | None = None
) -> None:
    """Stream ``url`` to ``destination``, emitting download progress events."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, destination.open("wb") as handle:
        total_header = response.headers.get("Content-Length")
        total = int(total_header) if total_header else None
        downloaded = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            downloaded += len(chunk)
            if progress is not None:
                progress("download", "Downloading taxdump", downloaded, total, False)
    if progress is not None:
        progress("download", "Downloaded taxdump", downloaded, total, True)


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
        row = con.execute(
            "SELECT value FROM metadata WHERE key = ?", (_SOURCE_MD5_KEY,)
        ).fetchone()
        return row[0] if row and row[0] else None
    except sqlite3.Error:
        return None
    finally:
        con.close()


def check_for_update(path: str | Path, *, url: str = DEFAULT_TAXDUMP_URL) -> bool | None:
    """Notify (never replace) whether a newer NCBI taxonomy release exists.

    Compares the digest of the taxdump this DB was built from against NCBI's
    current published MD5. Returns True if a newer release is available, False if
    current, and None if it could not be determined (older DB or network error).
    Decision 3: notify, never auto-replace — the caller rebuilds with refresh=True.
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


def _check_disk(target_dir: Path) -> None:
    """Fail early with a clear message if there is not enough free disk to build."""
    target_dir.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(target_dir).free
    if free < _MIN_FREE_BYTES:
        raise BackendConfigurationError(
            f"insufficient disk space to build taxonomy DB under {target_dir}: "
            f"need ~{_MIN_FREE_BYTES // 1024**3} GB free, have {free // 1024**3} GB"
        )


class _BuildLock:
    """A best-effort cross-process lock so two builds never target the same path."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path.with_name(db_path.name + ".lock")

    def __enter__(self) -> "_BuildLock":
        while True:
            try:
                fd = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if self._reclaim_if_stale():
                    continue
                time.sleep(_LOCK_POLL_SECONDS)
                continue
            os.write(fd, str(os.getpid()).encode("ascii"))
            os.close(fd)
            return self

    def __exit__(self, *_exc: object) -> None:
        try:
            self._path.unlink()
        except FileNotFoundError:
            pass

    def _reclaim_if_stale(self) -> bool:
        """Remove the lock if it is older than the staleness window (a crashed build)."""
        try:
            age = time.time() - self._path.stat().st_mtime
        except FileNotFoundError:
            return True  # lock vanished — retry acquisition immediately
        if age > _LOCK_STALE_SECONDS:
            logger.warning("reclaiming stale build lock %s (age %.0fs)", self._path, age)
            try:
                self._path.unlink()
            except FileNotFoundError:
                pass
            return True
        return False


def _build_into_place(
    db_path: Path, *, url: str, progress: ProgressCallback | None
) -> None:
    """Download → verify → build → validate → atomically publish to ``db_path``."""
    _check_disk(db_path.parent)
    logger.info("acquiring NCBI taxonomy DB -> %s (source: %s)", db_path, url)
    # Build inside a temp dir on the same filesystem so the final rename is atomic.
    with tempfile.TemporaryDirectory(dir=db_path.parent) as tmp:
        tmp_dir = Path(tmp)
        archive = tmp_dir / "taxdump.tar.gz"
        _download(url, archive, progress=progress)
        archive_md5 = _verify_download(archive, url)
        tmp_db = tmp_dir / "taxonomy.sqlite"
        summary = build_taxonomy_database(archive, tmp_db, progress_callback=progress)
        if not all(summary.validation_checks.values()):
            raise BackendConfigurationError(
                f"built taxonomy DB failed validation: {summary.validation_checks}"
            )
        # Record the source digest so check_for_update() can later detect staleness.
        upsert_metadata(tmp_db, {_SOURCE_MD5_KEY: archive_md5})
        os.replace(tmp_db, db_path)
    logger.info(
        "taxonomy DB ready: %s (build %s)", db_path, summary.taxonomy_build_version
    )


def ensure_taxonomy_db(
    path: str | Path | None = None,
    *,
    auto: bool = False,
    refresh: bool = False,
    url: str = DEFAULT_TAXDUMP_URL,
    progress: ProgressCallback | None = None,
) -> Path:
    """Ensure a valid local taxonomy DB exists, returning its path.

    Idempotent: a valid DB present (and ``refresh`` is False) returns instantly.
    Otherwise the DB must be acquired, which requires consent (``auto=True`` or
    ``BRAIDWORKS_AUTO_DOWNLOAD``); without it an actionable error is raised.
    Acquisition runs under a lock and publishes atomically.
    """
    db_path = Path(path) if path is not None else default_db_path()
    if db_is_valid(db_path) and not refresh:
        return db_path
    if not auto_consented(auto):
        raise BackendConfigurationError(_consent_message(db_path))

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _BuildLock(db_path):
        # Another process may have finished building while we waited for the lock.
        if db_is_valid(db_path) and not refresh:
            return db_path
        _build_into_place(db_path, url=url, progress=progress)
    return db_path
