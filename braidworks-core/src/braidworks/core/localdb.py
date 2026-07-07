"""Generic plumbing for acquiring a large local data file into the user cache.

Domain-neutral mechanics shared by any weaver whose backend reads a multi-GB local
artifact built from a download: default cache-path resolution, the opt-in consent
gate, a streamed download, an MD5 integrity check, a disk precheck, a best-effort
cross-process build lock, and an atomically-published build.

It is **callback-shaped**: :func:`ensure_local_db` owns the orchestration (validity →
consent → lock → disk → atomic publish) and the caller supplies the domain-specific
pieces — how to *build* the file and how to tell whether one is *valid*. The first
real user is ``ncbi_weaver``'s ``ensure_taxonomy_db``; keep this neutral (no NCBI /
taxonomy assumptions) so the next bulk weaver can reuse it.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

from platformdirs import user_cache_dir

from braidworks.core.exceptions import BackendConfigurationError

logger = logging.getLogger("braidworks.core.localdb")

ENV_DATA_DIR = "BRAIDWORKS_DATA_DIR"
ENV_AUTO = "BRAIDWORKS_AUTO_DOWNLOAD"
_TRUTHY = {"1", "true", "yes", "on"}

# Identify braidworks on downloads. The ``Mozilla/5.0`` prefix is what CDN bot-filters
# (e.g. Cloudflare in front of VMH/AGORA2) expect; without it they 403 the default agent.
USER_AGENT = "Mozilla/5.0 (compatible; braidworks/1.0)"

DEFAULT_MIN_FREE_BYTES = 4 * 1024**3
LOCK_STALE_SECONDS = 2 * 60 * 60
LOCK_POLL_SECONDS = 1.0

# (phase, message, done_bytes, total_bytes|None, finished) — a generic progress event.
ProgressCallback = Callable[[str, str, int, "int | None", bool], None]


def default_db_path(namespace: str, filename: str) -> Path:
    """Per-user default path ``<cache>/<namespace>/<filename>``.

    ``BRAIDWORKS_DATA_DIR`` overrides the platform cache dir (useful for tests and
    shared installs).
    """
    override = os.environ.get(ENV_DATA_DIR)
    base = Path(override) if override else Path(user_cache_dir("braidworks"))
    return base / namespace / filename


def auto_consented(auto: bool) -> bool:
    """Whether heavy acquisition is consented to (explicit flag or env var)."""
    if auto:
        return True
    return os.environ.get(ENV_AUTO, "").strip().lower() in _TRUTHY


def md5_file(path: Path) -> str:
    """Compute the MD5 of a local file (many sources publish an MD5 sidecar)."""
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_remote_md5(url: str) -> str | None:
    """Fetch and parse a published ``<url>.md5`` digest; None if unavailable."""
    try:
        with urllib.request.urlopen(f"{url}.md5") as response:
            text = response.read().decode("utf-8")
    except (OSError, ValueError) as exc:  # network/URL errors — integrity check is best-effort
        logger.warning("could not fetch checksum %s.md5 (%s); skipping integrity check", url, exc)
        return None
    parts = text.split()
    return parts[0].lower() if parts else None


def download(
    url: str,
    destination: Path,
    *,
    progress: ProgressCallback | None = None,
    label: str = "Downloading",
) -> None:
    """Stream ``url`` to ``destination``, emitting progress events.

    Sends an explicit ``User-Agent``: some data hosts sit behind a CDN (e.g. VMH/AGORA2
    behind Cloudflare) that 403s the default ``Python-urllib`` agent. Identify as braidworks
    with a browser-recognizable prefix so those sources serve the file.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request) as response, destination.open("wb") as handle:
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
                progress("download", label, downloaded, total, False)
    if progress is not None:
        progress("download", label, downloaded, total, True)


def check_disk(target_dir: Path, *, min_free_bytes: int = DEFAULT_MIN_FREE_BYTES) -> None:
    """Fail early with a clear message if there isn't enough free disk to build."""
    target_dir.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(target_dir).free
    if free < min_free_bytes:
        raise BackendConfigurationError(
            f"insufficient disk space to build under {target_dir}: "
            f"need ~{min_free_bytes // 1024**3} GB free, have {free // 1024**3} GB"
        )


class BuildLock:
    """A best-effort cross-process lock so two builds never target the same path."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path.with_name(db_path.name + ".lock")

    def __enter__(self) -> "BuildLock":
        while True:
            try:
                fd = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if self._reclaim_if_stale():
                    continue
                time.sleep(LOCK_POLL_SECONDS)
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
        """Remove the lock if older than the staleness window (a crashed build)."""
        try:
            age = time.time() - self._path.stat().st_mtime
        except FileNotFoundError:
            return True  # lock vanished — retry acquisition immediately
        if age > LOCK_STALE_SECONDS:
            logger.warning("reclaiming stale build lock %s (age %.0fs)", self._path, age)
            try:
                self._path.unlink()
            except FileNotFoundError:
                pass
            return True
        return False


def ensure_local_db(
    db_path: Path,
    *,
    is_valid: Callable[[Path], bool],
    build: Callable[[Path], None],
    consent_message: str,
    auto: bool = False,
    refresh: bool = False,
    min_free_bytes: int = DEFAULT_MIN_FREE_BYTES,
) -> Path:
    """Ensure a valid local DB exists at ``db_path``, returning its path.

    Orchestration only — the caller supplies the domain pieces:

    - ``is_valid(path)`` — whether ``path`` is a usable, fully-built DB.
    - ``build(tmp_path)`` — build the DB into ``tmp_path`` (download / verify /
      construct / record provenance). Raise on any failure; nothing is published.
    - ``consent_message`` — the actionable error when acquisition is needed but
      consent was not given.

    Idempotent: a valid DB present (and ``refresh`` False) returns instantly.
    Otherwise acquisition requires consent (``auto`` or ``BRAIDWORKS_AUTO_DOWNLOAD``),
    runs under a cross-process lock, prechecks disk, and publishes atomically (build
    into a temp dir on the same filesystem, then ``os.replace``) so a crash never
    leaves a half-written DB in place.
    """
    if is_valid(db_path) and not refresh:
        return db_path
    if not auto_consented(auto):
        raise BackendConfigurationError(consent_message)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with BuildLock(db_path):
        # Another process may have finished building while we waited for the lock.
        if is_valid(db_path) and not refresh:
            return db_path
        check_disk(db_path.parent, min_free_bytes=min_free_bytes)
        # Build on the same filesystem so the final rename is atomic.
        with tempfile.TemporaryDirectory(dir=db_path.parent) as tmp:
            tmp_db = Path(tmp) / db_path.name
            build(tmp_db)
            if not is_valid(tmp_db):
                raise BackendConfigurationError(
                    f"built DB at {tmp_db} failed validation (is_valid returned False)"
                )
            os.replace(tmp_db, db_path)
    return db_path
