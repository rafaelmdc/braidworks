"""ensure_gtdb_db — acquiring the local NCBI→GTDB crosswalk (gtdb_weaver-specific).

The generic mechanics — consent gate, streamed download, disk precheck, build lock,
atomic publish — live in ``braidworks.core.localdb``. This module supplies only the
GTDB specifics: the metadata source URLs (bac120 + ar53), what makes a built DB
*valid*, and the build itself (stream the gzipped metadata TSVs → the small crosswalk
SQLite via ``taxonomy.build_crosswalk_db``, recording the GTDB release).

Interactive entry points obtain consent by prompting, then call this with ``auto=True``.
This function never prompts, so it stays deterministic and easy to test.
"""

from __future__ import annotations

import csv
import gzip
import logging
import sqlite3
import urllib.request
from pathlib import Path
from typing import Iterator

from braidworks.core.localdb import auto_consented
from braidworks.core.localdb import default_db_path as _core_default_db_path
from braidworks.core.localdb import download as _download
from braidworks.core.localdb import ensure_local_db

from gtdb_weaver import taxonomy

logger = logging.getLogger("gtdb_weaver.setup")

_BASE = "https://data.gtdb.ecogenomic.org/releases/latest"
DEFAULT_BAC120_URL = f"{_BASE}/bac120_metadata.tsv.gz"
DEFAULT_AR53_URL = f"{_BASE}/ar53_metadata.tsv.gz"
# Newick reference trees — the source for tree placement (patristic distance). Leaves are
# representative genome accessions. Filenames verified against the live release (GTDB R232)
# by the tree backend's E2E (tests/test_e2e_live.py).
DEFAULT_BAC120_TREE_URL = f"{_BASE}/bac120.tree"
DEFAULT_AR53_TREE_URL = f"{_BASE}/ar53.tree"
_VERSION_URL = f"{_BASE}/VERSION.txt"

_NAMESPACE = "gtdb"
_DB_FILENAME = "gtdb_crosswalk.sqlite"
# Two gzipped metadata TSVs (~150 MB combined) streamed, plus a small SQLite; a
# modest margin covers the temporary downloads and the build.
_MIN_FREE_BYTES = 2 * 1024**3

__all__ = [
    "DEFAULT_AR53_TREE_URL",
    "DEFAULT_AR53_URL",
    "DEFAULT_BAC120_TREE_URL",
    "DEFAULT_BAC120_URL",
    "auto_consented",
    "db_is_valid",
    "default_db_path",
    "default_tree_paths",
    "ensure_gtdb_db",
    "ensure_gtdb_trees",
]


def default_db_path() -> Path:
    """Per-user default crosswalk DB path (``BRAIDWORKS_DATA_DIR`` overrides the cache dir)."""
    return _core_default_db_path(_NAMESPACE, _DB_FILENAME)


def default_tree_paths() -> list[Path]:
    """Per-user default reference-tree paths (bac120, ar53), beside the crosswalk DB."""
    parent = default_db_path().parent
    return [parent / "bac120.tree", parent / "ar53.tree"]


def ensure_gtdb_trees(
    *,
    auto: bool = False,
    refresh: bool = False,
    urls: tuple[str, str] = (DEFAULT_BAC120_TREE_URL, DEFAULT_AR53_TREE_URL),
) -> list[Path]:
    """Ensure the local Newick reference trees exist, returning their paths.

    Each tree is downloaded (consent-gated, like the crosswalk) if absent. Idempotent:
    a present, non-empty tree is returned as-is. Trees are plain files, so "valid" is
    simply "exists and non-empty".
    """

    def _valid(path: Path) -> bool:
        return path.exists() and path.stat().st_size > 0

    out: list[Path] = []
    for target, url in zip(default_tree_paths(), urls):
        ensure_local_db(
            target,
            is_valid=_valid,
            build=lambda dest, u=url: _download(u, dest, label=f"Downloading GTDB tree {u}"),
            consent_message=(
                f"GTDB reference tree not found at {target}.\n"
                "Tree placement (patristic distance) needs the GTDB Newick reference trees.\n"
                "  - call: build_gtdb_weaver(auto_setup=True, enable_tree_placement=True)\n"
                "  - or set: BRAIDWORKS_AUTO_DOWNLOAD=1"
            ),
            auto=auto,
            refresh=refresh,
            min_free_bytes=_MIN_FREE_BYTES,
        )
        out.append(target)
    return out


def db_is_valid(path: Path) -> bool:
    """Return whether ``path`` is a readable, populated crosswalk DB."""
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        return con.execute("SELECT 1 FROM taxon LIMIT 1").fetchone() is not None
    except sqlite3.Error:
        return False
    finally:
        con.close()


def _consent_message(db_path: Path) -> str:
    return (
        f"GTDB crosswalk database not found at {db_path}.\n"
        "The local backend needs a SQLite NCBI→GTDB crosswalk (~tens of MB, built by\n"
        "streaming the GTDB metadata TSVs, ~150 MB download). To create it:\n"
        "  - call: build_gtdb_weaver(auto_setup=True)\n"
        "  - or set: BRAIDWORKS_AUTO_DOWNLOAD=1\n"
        "Or build it yourself and pass db_path= to build_gtdb_weaver()."
    )


def _fetch_release() -> str | None:
    """The current GTDB release tag from the published VERSION.txt (e.g. ``R226``), if reachable."""
    try:
        with urllib.request.urlopen(_VERSION_URL, timeout=30) as resp:
            first = resp.read().decode("utf-8", "replace").splitlines()
        for line in first:
            token = line.strip()
            if token:
                return token.split()[0]
    except Exception as exc:  # network/parse — non-fatal, the tag is only informational
        logger.info("could not read GTDB VERSION.txt: %s", exc)
    return None


def _iter_metadata_rows(gz_path: Path) -> Iterator[tuple[int, str, bool, str]]:
    """Stream ``(ncbi_taxid, gtdb_taxonomy, is_rep, accession)`` from a gzipped metadata TSV.

    Columns are located by header name (their ordinal positions drift across releases).
    ``accession`` is the genome id GTDB labels its reference-tree leaves with — kept so a
    species representative can be joined to its leaf. Rows without an integer taxid or a
    taxonomy are skipped.
    """
    with gzip.open(gz_path, mode="rt", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh, delimiter="\t")
        header = next(reader, None)
        if not header:
            return
        idx = {name: i for i, name in enumerate(header)}
        try:
            c_taxid = idx["ncbi_taxid"]
            c_tax = idx["gtdb_taxonomy"]
            c_rep = idx["gtdb_representative"]
            c_acc = idx["accession"]
        except KeyError as exc:
            raise ValueError(f"GTDB metadata missing expected column {exc}") from exc
        width = max(c_taxid, c_tax, c_rep, c_acc) + 1
        for row in reader:
            if len(row) < width:
                continue
            raw_taxid = row[c_taxid].strip()
            taxonomy_str = row[c_tax].strip()
            if not taxonomy_str:
                continue
            try:
                taxid = int(raw_taxid)
            except ValueError:
                continue
            is_rep = row[c_rep].strip().lower() in {"t", "true", "1"}
            yield taxid, taxonomy_str, is_rep, row[c_acc].strip()


def _build_crosswalk(tmp_db: Path, *, bac120_url: str, ar53_url: str, release: str | None) -> None:
    """Build callback for ``ensure_local_db``: download both TSVs → the crosswalk SQLite."""
    resolved_release = release or _fetch_release() or "latest"
    rows: list[tuple[int, str, bool, str]] = []
    for label, url in (("bac120", bac120_url), ("ar53", ar53_url)):
        archive = tmp_db.parent / f"{label}_metadata.tsv.gz"
        logger.info("acquiring GTDB %s metadata -> %s", label, archive)
        _download(url, archive, label=f"Downloading GTDB {label} metadata")
        rows.extend(_iter_metadata_rows(archive))
        archive.unlink(missing_ok=True)
    if not rows:
        raise ValueError("no rows parsed from GTDB metadata (download corrupt?)")
    taxonomy.build_crosswalk_db(rows, tmp_db, release=resolved_release)
    logger.info(
        "GTDB crosswalk built: %s (%d taxa, release %s)", tmp_db, len(rows), resolved_release
    )


def ensure_gtdb_db(
    path: str | Path | None = None,
    *,
    auto: bool = False,
    refresh: bool = False,
    bac120_url: str = DEFAULT_BAC120_URL,
    ar53_url: str = DEFAULT_AR53_URL,
    release: str | None = None,
) -> Path:
    """Ensure a valid local crosswalk DB exists, returning its path.

    Idempotent: a valid DB present (and ``refresh`` False) returns instantly.
    Otherwise acquisition requires consent (``auto=True`` or ``BRAIDWORKS_AUTO_DOWNLOAD``);
    without it an actionable error is raised. Locking, disk precheck, and atomic publish
    are handled by ``braidworks.core.localdb.ensure_local_db``.
    """
    db_path = Path(path) if path is not None else default_db_path()
    return ensure_local_db(
        db_path,
        is_valid=db_is_valid,
        build=lambda target: _build_crosswalk(
            target, bac120_url=bac120_url, ar53_url=ar53_url, release=release
        ),
        consent_message=_consent_message(db_path),
        auto=auto,
        refresh=refresh,
        min_free_bytes=_MIN_FREE_BYTES,
    )
