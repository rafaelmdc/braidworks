"""Generic plumbing for acquiring a large local data file into the user cache.

Domain-neutral mechanics shared by any weaver whose backend reads a multi-GB local
artifact built from a download: default cache-path resolution, the opt-in consent
gate, a streamed download, an MD5 integrity check, a disk precheck, an OS-owned
cross-process build lock, and an atomically-published build.

It is **callback-shaped**: :func:`ensure_local_db` owns the orchestration (validity →
consent → lock → disk → atomic publish) and the caller supplies the domain-specific
pieces — how to *build* the file and how to tell whether one is *valid*. The first
real user is ``ncbi_weaver``'s ``ensure_taxonomy_db``; keep this neutral (no NCBI /
taxonomy assumptions) so the next bulk weaver can reuse it.
"""

from __future__ import annotations

import errno
import hashlib
import logging
import math
import os
import shutil
import sys
import tempfile
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Self

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
LOCK_STALE_SECONDS = 2 * 60 * 60  # Legacy public constant; age never determines ownership.
LOCK_TIMEOUT_SECONDS = 2 * 60 * 60
LOCK_POLL_SECONDS = 1.0
DOWNLOAD_TIMEOUT_SECONDS = 30.0
PROGRESS_INTERVAL_SECONDS = 10.0

# (phase, message, done_bytes, total_bytes|None, finished) — a generic progress event.
ProgressCallback = Callable[[str, str, int, "int | None", bool], None]


def _stderr_progress() -> ProgressCallback:
    """Create a throttled reporter for one acquisition, leaving stdout for results."""
    last_report = float("-inf")
    last_stage = None

    def report(phase, message, done, total, finished):
        nonlocal last_report, last_stage
        now = time.monotonic()
        stage = (phase, message)
        if not finished and stage == last_stage and now - last_report < PROGRESS_INTERVAL_SECONDS:
            return
        last_stage, last_report = stage, now
        count = (
            f" ({done}/{total} bytes)"
            if total is not None
            else (f" ({done} bytes)" if done else "")
        )
        status = "done" if finished else "in progress"
        print(f"braidworks: {phase}: {message}{count} [{status}]", file=sys.stderr, flush=True)

    return report


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
        with urllib.request.urlopen(f"{url}.md5", timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            text = response.read().decode("utf-8")
    except (OSError, ValueError) as exc:  # network/URL errors — integrity check is best-effort
        logger.warning(
            "could not fetch checksum (%s); skipping integrity check", type(exc).__name__
        )
        return None
    parts = text.split()
    return parts[0].lower() if parts else None


def download(
    url: str,
    destination: Path,
    *,
    progress: ProgressCallback | None = None,
    label: str = "Downloading",
    timeout: float = DOWNLOAD_TIMEOUT_SECONDS,
) -> None:
    """Stream ``url`` to ``destination``, emitting progress events.

    With no callback, report initial/periodic/final progress to stderr. Supply a
    no-op callback for quiet operation. ``timeout`` limits socket inactivity, not
    the total transfer duration; requests are not retried.

    Sends an explicit ``User-Agent``: some data hosts sit behind a CDN (e.g. VMH/AGORA2
    behind Cloudflare) that 403s the default ``Python-urllib`` agent. Identify as braidworks
    with a browser-recognizable prefix so those sources serve the file.
    """
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Download timeout must be finite and positive")
    report = progress if progress is not None else _stderr_progress()
    report("download", label, 0, None, False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    downloaded = 0
    total = None
    try:
        with (
            urllib.request.urlopen(request, timeout=timeout) as response,
            destination.open("wb") as handle,
        ):
            total_header = response.headers.get("Content-Length")
            total = int(total_header) if total_header else None
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                report("download", label, downloaded, total, False)
    except Exception:
        report("failed", label, downloaded, total, True)
        raise
    report("download", label, downloaded, total, True)


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
    """Process-owned advisory lock (POSIX flock / Windows byte-range lock).

    The stable lock file remains after release: unlinking it lets a contender lock
    a different inode. Kernel ownership survives long builds and ends on process
    death. Use only on a local filesystem with working OS advisory locks.
    """

    def __init__(
        self,
        db_path: Path,
        *,
        timeout: float = LOCK_TIMEOUT_SECONDS,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout < 0:
            raise ValueError("Build-lock timeout must be finite and nonnegative")
        self._path = db_path.with_name(db_path.name + ".lock")
        self._timeout = timeout
        self._progress = progress
        self._handle = None

    def __enter__(self) -> Self:
        if self._handle is not None:
            raise RuntimeError("BuildLock is already acquired")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._path.open("a+b")
        if os.name == "nt" and self._path.stat().st_size == 0:
            # Windows locking requires an existing byte.
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic() + self._timeout
        try:
            while True:
                try:
                    if os.name == "posix":
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    elif os.name == "nt":
                        import msvcrt

                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        raise BackendConfigurationError("OS build locks require POSIX or Windows")
                    break
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise BackendConfigurationError(
                            f"Timed out waiting for build lock {self._path}"
                        ) from exc
                    if self._progress is not None:
                        self._progress(f"Waiting for build lock {self._path}")
                    time.sleep(min(LOCK_POLL_SECONDS, remaining))
            self._handle = handle
            return self
        except BaseException:
            handle.close()
            raise

    def __exit__(self, *_exc: object) -> None:
        if self._handle is not None:
            # Closing this exact handle releases only this owner's kernel lock.
            self._handle.close()
            self._handle = None


def ensure_local_db(
    db_path: Path,
    *,
    is_valid: Callable[[Path], bool],
    build: Callable[[Path], None],
    consent_message: str,
    auto: bool = False,
    refresh: bool = False,
    min_free_bytes: int = DEFAULT_MIN_FREE_BYTES,
    progress: ProgressCallback | None = None,
) -> Path:
    """Ensure a valid local DB exists at ``db_path``, returning its path.

    Orchestration only — the caller supplies the domain pieces:

    - ``is_valid(path)`` — whether ``path`` is a usable, fully-built DB.
    - ``build(tmp_path)`` — build the DB into ``tmp_path`` (download / verify /
      construct / record provenance). Raise on any failure; nothing is published.
    - ``consent_message`` — the actionable error when acquisition is needed but
      consent was not given.

    With no callback, acquisition/build and lock-wait progress goes to stderr.
    A callback replaces those events; downloads within ``build`` have their own
    progress callback. Existing valid artifacts produce no progress output.

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
    report = progress if progress is not None else _stderr_progress()
    report("acquire", str(db_path), 0, None, False)
    with BuildLock(db_path, progress=lambda message: report("wait", message, 0, None, False)):
        # Another process may have finished building while we waited for the lock.
        if is_valid(db_path) and not refresh:
            report("acquire", str(db_path), 0, None, True)
            return db_path
        check_disk(db_path.parent, min_free_bytes=min_free_bytes)
        # Build on the same filesystem so the final rename is atomic.
        with tempfile.TemporaryDirectory(dir=db_path.parent) as tmp:
            tmp_db = Path(tmp) / db_path.name
            report("build", str(db_path), 0, None, False)
            try:
                build(tmp_db)
                if not is_valid(tmp_db):
                    raise BackendConfigurationError(
                        f"built DB at {tmp_db} failed validation (is_valid returned False)"
                    )
                os.replace(tmp_db, db_path)
            except Exception:
                report("failed", str(db_path), 0, None, True)
                raise
            report("build", str(db_path), 0, None, True)
    return db_path
