"""Local MONDO DB acquisition: download the OBO release once and build a small SQLite
the ``local`` backend serves offline.

MONDO ships a single ~53 MB OBO release (``mondo.obo``) carrying every disease term,
its ``is_a`` edges, and cross-references to MeSH / MedDRA / DOID / OMIM. We parse it once
into three tables — ``term`` (id → name), ``isa`` (child → parent), and ``xref``
(source, external id → MONDO id) — then serve offline; ``is_a`` ancestors are walked with
a recursive query at lookup time, so the DB stays small.

The generic acquisition plumbing (consent gate, cross-process lock, disk precheck, atomic
publish) lives in ``braidworks.core.localdb``; this module supplies the domain pieces —
``db_is_valid`` and ``_build`` — plus the OBO download and parse.
"""

from __future__ import annotations

import re
import sqlite3
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Callable

from braidworks.core.localdb import ProgressCallback, default_db_path, ensure_local_db

OBO_URL = "http://purl.obolibrary.org/obo/mondo.obo"
NAMESPACE = "mondo"
DB_FILENAME = "mondo.sqlite"
_FETCH_TIMEOUT = 300  # seconds; the OBO is ~53 MB
_USER_AGENT = "braidworks/mondo_weaver (+https://github.com/rafaelmdc/braidworks)"

# xref sources we index as disease entry points, mapped to their SHARED_KEY source tag.
_INDEXED_SOURCES = {"MESH": "MESH", "MedDRA": "MedDRA"}
_MONDO_RE = re.compile(r"\bMONDO:\d+")

_CONSENT_MESSAGE = (
    "mondo_weaver's local DB is not built yet ({path}).\n"
    "It downloads the ~53 MB MONDO OBO release and builds a small SQLite (a minute or two), "
    "but acquisition is opt-in. To build it:\n"
    "  - call build_mondo_weaver_configured(auto_setup=True), or\n"
    "  - set BRAIDWORKS_AUTO_DOWNLOAD=1, or\n"
    "  - call mondo_weaver.setup.ensure_mondo_db(auto=True).\n"
    "Override the location with db_path=... or the BRAIDWORKS_DATA_DIR env var."
)


def default_mondo_db_path() -> Path:
    """Per-user default DB path (override via ``BRAIDWORKS_DATA_DIR``)."""
    return default_db_path(NAMESPACE, DB_FILENAME)


def normalize_xref(source: str, xref_id: str) -> tuple[str, str] | None:
    """Normalize a (source, id) pair to an indexed (SOURCE_TAG, id), or None if unindexed.

    GMrepo hands us bare MeSH ids like ``D003093``; Disbiome hands MedDRA ids like
    ``10080683``. Both are stored without the ontology prefix (the source column carries it).
    """
    tag = _INDEXED_SOURCES.get(source)
    if tag is None:
        return None
    return tag, xref_id.strip()


_SYNONYM_RE = re.compile(r'"((?:[^"\\]|\\.)*)"\s+(EXACT|NARROW|BROAD|RELATED)')


def normalize_name(name: str) -> str:
    """Normalize a disease name/synonym for case- and whitespace-insensitive matching."""
    return " ".join(name.lower().split())


class _Term:
    __slots__ = ("mondo_id", "name", "obsolete", "parents", "xrefs", "synonyms")

    def __init__(self, mondo_id: str) -> None:
        self.mondo_id = mondo_id
        self.name: str | None = None
        self.obsolete = False
        self.parents: list[str] = []
        self.xrefs: list[tuple[str, str, bool]] = []  # (source_tag, id, is_equivalent)
        self.synonyms: list[str] = []  # EXACT synonym strings only


def _parse_obo(lines: Iterator[str]) -> tuple[str | None, list[_Term]]:
    """Parse an OBO stream into (data_version, [non-obsolete Term])."""
    data_version: str | None = None
    terms: list[_Term] = []
    current: _Term | None = None
    in_term = False

    for raw in lines:
        line = raw.rstrip("\n")
        if line.startswith("data-version:") and data_version is None:
            data_version = line.split(":", 1)[1].strip()
            continue
        if line.startswith("["):
            if current is not None and not current.obsolete and current.name:
                terms.append(current)
            in_term = line == "[Term]"
            current = None
            continue
        if not in_term or not line:
            continue
        key, _, value = line.partition(": ")
        if key == "id" and value.startswith("MONDO:"):
            current = _Term(value.strip())
        elif current is None:
            continue
        elif key == "name":
            current.name = value.strip()
        elif key == "is_obsolete" and value.strip() == "true":
            current.obsolete = True
        elif key == "is_a":
            match = _MONDO_RE.search(value)
            if match:
                current.parents.append(match.group(0))
        elif key == "synonym":
            match = _SYNONYM_RE.match(value)
            if match and match.group(2) == "EXACT":
                current.synonyms.append(match.group(1).replace('\\"', '"'))
        elif key == "xref":
            token = value.split(" ", 1)[0]
            source, _, xref_id = token.partition(":")
            norm = normalize_xref(source, xref_id)
            if norm is not None:
                current.xrefs.append((norm[0], norm[1], "MONDO:equivalentTo" in value))
    if current is not None and not current.obsolete and current.name:
        terms.append(current)
    return data_version, terms


def write_db(target: Path, *, data_version: str | None, terms: list[_Term]) -> None:
    """Build the SQLite at ``target`` from parsed MONDO terms (shared by build + fixture)."""
    valid_ids = {t.mondo_id for t in terms}
    con = sqlite3.connect(target)
    try:
        con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        con.execute("CREATE TABLE term (mondo_id TEXT PRIMARY KEY, name TEXT)")
        con.execute("CREATE TABLE isa (child TEXT, parent TEXT)")
        con.execute(
            "CREATE TABLE xref (source TEXT, xref_id TEXT, mondo_id TEXT, is_equivalent INTEGER)"
        )
        # name index: normalized label/exact-synonym -> mondo id (priority 0=label, 1=synonym).
        con.execute("CREATE TABLE name (norm TEXT, mondo_id TEXT, priority INTEGER)")
        con.executemany(
            "INSERT OR IGNORE INTO term VALUES (?, ?)",
            [(t.mondo_id, t.name) for t in terms],
        )
        name_rows: list[tuple[str, str, int]] = []
        for t in terms:
            if t.name:
                name_rows.append((normalize_name(t.name), t.mondo_id, 0))
            for syn in t.synonyms:
                name_rows.append((normalize_name(syn), t.mondo_id, 1))
        con.executemany("INSERT INTO name VALUES (?, ?, ?)", name_rows)
        con.executemany(
            "INSERT INTO isa VALUES (?, ?)",
            [(t.mondo_id, p) for t in terms for p in t.parents if p in valid_ids],
        )
        con.executemany(
            "INSERT INTO xref VALUES (?, ?, ?, ?)",
            [(src, xid, t.mondo_id, int(eq)) for t in terms for (src, xid, eq) in t.xrefs],
        )
        con.execute("CREATE INDEX ix_isa_child ON isa(child)")
        con.execute("CREATE INDEX ix_xref_lookup ON xref(source, xref_id)")
        con.execute("CREATE INDEX ix_name_lookup ON name(norm)")
        n_edges = con.execute("SELECT COUNT(*) FROM isa").fetchone()[0]
        n_xref = con.execute("SELECT COUNT(*) FROM xref").fetchone()[0]
        con.executemany(
            "INSERT INTO meta VALUES (?, ?)",
            [
                ("data_version", data_version or "unknown"),
                ("n_terms", str(len(terms))),
                ("n_edges", str(n_edges)),
                ("n_xref", str(n_xref)),
                ("source", OBO_URL),
            ],
        )
        con.commit()
    finally:
        con.close()


def db_is_valid(path: Path) -> bool:
    """A usable, fully-built MONDO DB: has a data_version and non-empty terms + xrefs."""
    if not path.exists():
        return False
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        has_version = con.execute("SELECT value FROM meta WHERE key = 'data_version'").fetchone()
        n_terms = con.execute("SELECT COUNT(*) FROM term").fetchone()[0]
        n_xref = con.execute("SELECT COUNT(*) FROM xref").fetchone()[0]
        n_name = con.execute("SELECT COUNT(*) FROM name").fetchone()[0]  # 0.2.0 name index
        return bool(has_version) and n_terms > 0 and n_xref > 0 and n_name > 0
    except sqlite3.Error:
        return False
    finally:
        con.close()


def _download(target: Path, progress: ProgressCallback | None = None) -> None:
    """Stream the OBO release to ``target``."""
    request = urllib.request.Request(OBO_URL, headers={"User-Agent": _USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(request, timeout=_FETCH_TIMEOUT) as response:  # noqa: S310
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        with open(target, "wb") as fh:
            while chunk := response.read(1 << 20):
                fh.write(chunk)
                done += len(chunk)
                if progress and total:
                    progress(done, total, "downloading mondo.obo")


def _build(
    target: Path,
    *,
    download: Callable[[Path, ProgressCallback | None], None] = _download,
    progress: ProgressCallback | None = None,
) -> None:
    """Download + parse mondo.obo and write the SQLite at ``target`` (``download`` injectable)."""
    obo_path = target.with_suffix(".obo.tmp")
    try:
        download(obo_path, progress)
        with open(obo_path, encoding="utf-8") as fh:
            data_version, terms = _parse_obo(iter(fh))
        write_db(target, data_version=data_version, terms=terms)
    finally:
        obo_path.unlink(missing_ok=True)


def ensure_mondo_db(
    db_path: str | Path | None = None,
    *,
    auto: bool = False,
    refresh: bool = False,
    progress: ProgressCallback | None = None,
) -> Path:
    """Ensure a valid local MONDO SQLite exists, building it if consented.

    Idempotent: a valid DB is returned instantly. Otherwise acquisition needs consent
    (``auto`` or ``BRAIDWORKS_AUTO_DOWNLOAD``); without it, an actionable
    ``BackendConfigurationError`` is raised. ``refresh=True`` re-downloads.
    """
    path = Path(db_path) if db_path else default_mondo_db_path()

    def _build_with_progress(target: Path) -> None:
        _build(target, progress=progress)

    return ensure_local_db(
        path,
        is_valid=db_is_valid,
        build=_build_with_progress,
        consent_message=_CONSENT_MESSAGE.format(path=path),
        auto=auto,
        refresh=refresh,
        min_free_bytes=500_000_000,  # ~53 MB download + build headroom
    )
