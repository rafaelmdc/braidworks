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

import csv
import hashlib
import json
import re
import sqlite3
import urllib.request
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from graphlib import CycleError, TopologicalSorter
from pathlib import Path

from braidworks.core.localdb import ProgressCallback, default_db_path, ensure_local_db

OBO_URL = "https://purl.obolibrary.org/obo/mondo.obo"
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
    __slots__ = (
        "consider",
        "definition",
        "mondo_id",
        "name",
        "obsolete",
        "parents",
        "replaced_by",
        "synonyms",
        "xref_evidence",
        "xrefs",
    )

    def __init__(self, mondo_id: str) -> None:
        self.mondo_id = mondo_id
        self.name: str | None = None
        self.obsolete = False
        self.definition = None
        self.replaced_by = []
        self.consider = []
        self.parents: list[str] = []
        self.xrefs: list[tuple[str, str, bool]] = []  # (source_tag, id, is_equivalent)
        self.xref_evidence: list[tuple[str, str, str, str]] = []
        self.synonyms: list[str] = []  # EXACT synonym strings only


def _parse_obo(lines: Iterator[str]) -> tuple[str | None, list[_Term]]:
    """Parse an OBO stream into (data_version, [current and obsolete Term])."""
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
            if current is not None and current.name:
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
        elif key == "def":
            match = re.match(r'^"((?:[^"\\]|\\.)*)"', value)
            if match is None:
                raise ValueError("MONDO definition must be a quoted OBO string")
            current.definition = re.sub(
                r"\\(.)",
                lambda match: {"n": "\n", "r": "\r", "t": "\t"}.get(match[1], match[1]),
                match[1],
            )
        elif key in {"replaced_by", "consider"}:
            target = value.split()[0] if value.split() else ""
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*:[^\s]+", target):
                raise ValueError("MONDO history target must be a source identifier")
            getattr(current, key).append(target)
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
                predicates = set(re.findall(r"MONDO:[A-Za-z]+|skos:[A-Za-z]+", value))
                relation_codes = {
                    "MONDO:equivalentTo": "equivalent",
                    "skos:exactMatch": "exact_match",
                    "MONDO:mondoIsBroaderThanSource": "mondo_broader",
                    "MONDO:mondoIsNarrowerThanSource": "mondo_narrower",
                    "MONDO:relatedTo": "related",
                    "MONDO:directSiblingOf": "sibling",
                    "skos:broadMatch": "broad_match",
                    "skos:narrowMatch": "narrow_match",
                    "skos:relatedMatch": "related",
                    "skos:closeMatch": "close_match",
                }
                relations = sorted(
                    {
                        relation_codes[predicate]
                        for predicate in predicates
                        if predicate in relation_codes
                    }
                ) or ["unspecified"]
                relation = relations[0] if len(relations) == 1 else "conflicting"
                current.xrefs.append((norm[0], norm[1], relation == "equivalent"))
                current.xref_evidence.append((norm[0], norm[1], relation, value))
    if current is not None and current.name:
        terms.append(current)
    return data_version, terms


def _validate_graph(terms: list[_Term]) -> None:
    ids = {term.mondo_id for term in terms}
    if (
        len(ids) != len(terms)
        or not ids
        or any(not re.fullmatch(r"MONDO:\d+", identifier) for identifier in ids)
    ):
        raise ValueError("MONDO terms need distinct valid identifiers")
    if any(not term.name or any(parent not in ids for parent in term.parents) for term in terms):
        raise ValueError("MONDO graph has unnamed terms or dangling parents")
    try:
        TopologicalSorter({term.mondo_id: term.parents for term in terms}).prepare()
    except CycleError as exc:
        raise ValueError("MONDO is_a graph contains a cycle") from exc


def parse_sssom(lines: Iterator[str]) -> tuple[list[dict[str, str]], list[str]]:
    """Preserve canonical typed mapping rows and the complete metadata prelude."""
    metadata = []

    def data():
        for line in lines:
            if line.startswith("#"):
                metadata.append(line.rstrip("\n"))
            elif line.strip():
                yield line

    reader = csv.DictReader(data(), delimiter="\t")
    required = {"subject_id", "predicate_id", "object_id", "mapping_justification"}
    fields = reader.fieldnames
    if not fields or len(set(fields)) != len(fields) or not required <= set(fields):
        raise ValueError("MONDO SSSOM needs distinct headers and typed mapping columns")
    rows = {}
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Malformed MONDO SSSOM row width")
        if any(not row[key].strip() for key in required):
            raise ValueError("MONDO SSSOM has an incomplete typed mapping")
        if not re.fullmatch(r"MONDO:\d+", row["subject_id"]):
            raise ValueError("MONDO SSSOM subject must be a MONDO identifier")
        rows[json.dumps(row, sort_keys=True)] = row
    return [rows[key] for key in sorted(rows)], metadata


def _release_date(version: str | None) -> str:
    match = re.fullmatch(r"(?:releases/|v)?(\d{4}-\d{2}-\d{2})", version or "")
    if not match:
        raise ValueError("SSSOM ingestion requires a dated MONDO release")
    return match[1]


def write_db(
    target: Path,
    *,
    data_version: str | None,
    terms: list[_Term],
    source: dict | None = None,
    mappings: list[dict[str, str]] | None = None,
    mapping_source: dict | None = None,
) -> None:
    """Build the SQLite at ``target`` from parsed MONDO terms (shared by build + fixture)."""
    _validate_graph(terms)
    if source is None:
        normalized = [
            {
                "id": t.mondo_id,
                "name": t.name,
                "definition": t.definition,
                "obsolete": t.obsolete,
                "replaced_by": sorted(t.replaced_by),
                "consider": sorted(t.consider),
                "parents": sorted(t.parents),
                "xrefs": sorted(t.xrefs),
                "xref_evidence": sorted(t.xref_evidence),
                "synonyms": sorted(t.synonyms),
            }
            for t in sorted(terms, key=lambda t: t.mondo_id)
        ]
        source = {
            "kind": "caller-supplied-terms",
            "sha256": hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest(),
            "url": None,
        }
    if not re.fullmatch(r"[0-9a-f]{64}", source.get("sha256", "")):
        raise ValueError("MONDO source needs a SHA-256 identity")
    known_version = bool(
        data_version
        and data_version.strip()
        and data_version.strip().lower() not in {"unknown", "latest"}
    )
    version = data_version.strip() if known_version else "unversioned:sha256:" + source["sha256"]
    valid_ids = {t.mondo_id for t in terms}
    if mappings is not None:
        if not mapping_source or _release_date(mapping_source.get("release")) != _release_date(
            data_version
        ):
            raise ValueError("MONDO OBO and SSSOM releases must match")
        if not re.fullmatch(r"[0-9a-f]{64}", mapping_source.get("sha256", "")):
            raise ValueError("SSSOM source needs a SHA-256 identity")
        if any(row["subject_id"] not in valid_ids for row in mappings):
            raise ValueError("SSSOM has subjects missing from the OBO release")
    con = sqlite3.connect(target)
    try:
        con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        con.execute(
            "CREATE TABLE term (mondo_id TEXT PRIMARY KEY, name TEXT, definition TEXT, obsolete INTEGER NOT NULL, replaced_by TEXT NOT NULL, consider TEXT NOT NULL)"
        )
        con.execute("CREATE TABLE isa (child TEXT, parent TEXT)")
        con.execute(
            "CREATE TABLE xref (source TEXT, xref_id TEXT, mondo_id TEXT, is_equivalent INTEGER, "
            "relation TEXT NOT NULL DEFAULT 'unspecified', evidence TEXT)"
        )
        # name index: normalized label/exact-synonym -> mondo id (priority 0=label, 1=synonym).
        con.execute("CREATE TABLE name (norm TEXT, mondo_id TEXT, priority INTEGER)")
        con.execute("CREATE TABLE mapping (mondo_id TEXT NOT NULL, record TEXT NOT NULL)")
        con.executemany(
            "INSERT INTO mapping VALUES (?, ?)",
            [(row["subject_id"], json.dumps(row, sort_keys=True)) for row in mappings or []],
        )
        con.execute("CREATE INDEX ix_mapping_subject ON mapping(mondo_id)")
        con.executemany(
            "INSERT INTO term VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    t.mondo_id,
                    t.name,
                    t.definition,
                    int(t.obsolete),
                    json.dumps(sorted(set(t.replaced_by))),
                    json.dumps(sorted(set(t.consider))),
                )
                for t in terms
            ],
        )
        name_rows: list[tuple[str, str, int]] = []
        for t in terms:
            if t.obsolete:
                continue
            if t.name:
                name_rows.append((normalize_name(t.name), t.mondo_id, 0))
            for syn in t.synonyms:
                name_rows.append((normalize_name(syn), t.mondo_id, 1))
        con.executemany("INSERT INTO name VALUES (?, ?, ?)", name_rows)
        con.executemany(
            "INSERT INTO isa VALUES (?, ?)",
            [(t.mondo_id, p) for t in terms for p in t.parents if p in valid_ids],
        )
        xref_rows = set()
        for term in terms:
            if term.obsolete:
                continue
            observed = {(src, xid) for src, xid, relation, evidence in term.xref_evidence}
            for src, xid, relation, evidence in term.xref_evidence:
                xref_rows.add(
                    (src, xid, term.mondo_id, int(relation == "equivalent"), relation, evidence)
                )
            for src, xid, equivalent in term.xrefs:
                if (src, xid) not in observed:
                    relation = "equivalent" if equivalent else "unspecified"
                    xref_rows.add(
                        (src, xid, term.mondo_id, int(equivalent), relation, "caller-supplied")
                    )
        con.executemany("INSERT INTO xref VALUES (?, ?, ?, ?, ?, ?)", sorted(xref_rows))
        con.execute("CREATE INDEX ix_isa_child ON isa(child)")
        con.execute("CREATE INDEX ix_xref_lookup ON xref(source, xref_id)")
        con.execute("CREATE INDEX ix_name_lookup ON name(norm)")
        n_edges = con.execute("SELECT COUNT(*) FROM isa").fetchone()[0]
        n_xref = con.execute("SELECT COUNT(*) FROM xref").fetchone()[0]
        con.executemany(
            "INSERT INTO meta VALUES (?, ?)",
            [
                ("schema_version", "5"),
                ("build_id", uuid.uuid4().hex),
                ("data_version", version),
                ("release_known", str(known_version).lower()),
                ("source_sha256", source["sha256"]),
                ("source_descriptor", json.dumps(source, sort_keys=True)),
                ("mapping_source", json.dumps(mapping_source, sort_keys=True)),
                ("n_mappings", str(len(mappings or []))),
                ("n_terms", str(len(terms))),
                ("n_edges", str(n_edges)),
                ("n_xref", str(n_xref)),
                ("source", source.get("url") or "caller-supplied"),
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
        meta = dict(con.execute("SELECT key, value FROM meta"))
        if (
            meta.get("schema_version") != "5"
            or not re.fullmatch(r"[0-9a-f]{64}", meta.get("source_sha256", ""))
            or meta.get("data_version", "").lower() in {"", "unknown", "latest"}
        ):
            return False
        descriptor = json.loads(meta["source_descriptor"])
        if not isinstance(descriptor, dict) or descriptor.get("sha256") != meta["source_sha256"]:
            return False
        if meta.get("release_known") not in {"true", "false"}:
            return False
        if (
            meta["release_known"] == "false"
            and meta["data_version"] != "unversioned:sha256:" + meta["source_sha256"]
        ):
            return False
        if con.execute(
            "SELECT 1 FROM xref WHERE relation IS NULL OR is_equivalent != (relation = 'equivalent') LIMIT 1"
        ).fetchone():
            return False
        con.execute("SELECT definition, obsolete, replaced_by, consider FROM term LIMIT 0")
        terms = []
        by_id = {}
        for identifier, name in con.execute("SELECT mondo_id, name FROM term"):
            term = _Term(identifier)
            term.name = name
            terms.append(term)
            by_id[identifier] = term
        for child, parent in con.execute("SELECT child, parent FROM isa"):
            if child not in by_id or parent not in by_id:
                return False
            by_id[child].parents.append(parent)
        _validate_graph(terms)
        mapping_source = json.loads(meta["mapping_source"])
        if mapping_source is not None and (
            not isinstance(mapping_source, dict)
            or _release_date(mapping_source.get("release")) != _release_date(meta["data_version"])
            or not re.fullmatch(r"[0-9a-f]{64}", mapping_source.get("sha256", ""))
        ):
            return False
        counts = {
            "n_mappings": con.execute("SELECT COUNT(*) FROM mapping").fetchone()[0],
            "n_terms": len(terms),
            "n_edges": con.execute("SELECT COUNT(*) FROM isa").fetchone()[0],
            "n_xref": con.execute("SELECT COUNT(*) FROM xref").fetchone()[0],
        }
        if any(meta.get(key) != str(value) for key, value in counts.items()):
            return False
        for table in ("xref", "name", "mapping"):
            if con.execute(
                f"SELECT 1 FROM {table} t LEFT JOIN term ON t.mondo_id=term.mondo_id WHERE term.mondo_id IS NULL LIMIT 1"
            ).fetchone():
                return False
        return bool(con.execute("SELECT 1 FROM xref LIMIT 1").fetchone()) and bool(
            con.execute("SELECT 1 FROM name LIMIT 1").fetchone()
        )
    except (sqlite3.Error, ValueError, KeyError, TypeError):
        return False
    finally:
        con.close()


def _download(target: Path, progress: ProgressCallback | None = None) -> None:
    """Stream the OBO release to ``target``."""
    request = urllib.request.Request(OBO_URL, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=_FETCH_TIMEOUT) as response:
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
    expected_version: str | None = None,
    source_url: str | None = None,
    mapping_path: str | Path | None = None,
    mapping_release: str | None = None,
) -> None:
    """Download + parse mondo.obo and write the SQLite at ``target`` (``download`` injectable)."""
    obo_path = target.with_suffix(".obo.tmp")
    try:
        download(obo_path, progress)
        with open(obo_path, encoding="utf-8") as fh:
            data_version, terms = _parse_obo(iter(fh))
        if expected_version is not None and data_version != expected_version:
            raise ValueError(
                f"MONDO data-version mismatch: requested {expected_version!r}, observed {data_version!r}"
            )
        with obo_path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        mappings, mapping_source = None, None
        if mapping_path is not None:
            with Path(mapping_path).open(encoding="utf-8") as stream:
                mappings, metadata = parse_sssom(iter(stream))
            with Path(mapping_path).open("rb") as stream:
                mapping_hash = hashlib.file_digest(stream, "sha256").hexdigest()
            mapping_source = {
                "release": mapping_release,
                "sha256": mapping_hash,
                "path": str(Path(mapping_path).resolve()),
                "metadata": metadata,
                "kind": "caller-supplied-release-matched-sssom",
            }
        write_db(
            target,
            mappings=mappings,
            mapping_source=mapping_source,
            data_version=data_version,
            terms=terms,
            source={
                "kind": "obo",
                "sha256": digest,
                "url": source_url or (OBO_URL if download is _download else None),
                "acquired_at": datetime.now(UTC).isoformat(),
            },
        )
    finally:
        obo_path.unlink(missing_ok=True)


def ensure_mondo_db(
    db_path: str | Path | None = None,
    *,
    auto: bool = False,
    refresh: bool = False,
    progress: ProgressCallback | None = None,
    expected_version: str | None = None,
    mapping_path: str | Path | None = None,
    mapping_release: str | None = None,
) -> Path:
    """Ensure a valid local MONDO SQLite exists, building it if consented.

    Idempotent: a valid DB is returned instantly. Otherwise acquisition needs consent
    (``auto`` or ``BRAIDWORKS_AUTO_DOWNLOAD``); without it, an actionable
    ``BackendConfigurationError`` is raised. ``refresh=True`` re-downloads.
    """
    if (mapping_path is None) != (mapping_release is None):
        raise ValueError("Supply mapping_path and mapping_release together")
    mapping_hash = None
    if mapping_path is not None:
        _release_date(mapping_release)
        with Path(mapping_path).open("rb") as stream:
            mapping_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    path = Path(db_path) if db_path else default_mondo_db_path()

    def _build_with_progress(target: Path) -> None:
        _build(
            target,
            progress=progress,
            expected_version=expected_version,
            mapping_path=mapping_path,
            mapping_release=mapping_release,
        )

    def valid(target: Path) -> bool:
        if not db_is_valid(target):
            return False
        with sqlite3.connect(f"file:{target}?mode=ro", uri=True) as con:
            observed = con.execute("SELECT value FROM meta WHERE key='data_version'").fetchone()[0]
            mapping = json.loads(
                con.execute("SELECT value FROM meta WHERE key='mapping_source'").fetchone()[0]
            )
        return (expected_version is None or observed == expected_version) and (
            mapping_hash is None
            or (
                mapping is not None
                and mapping["sha256"] == mapping_hash
                and _release_date(mapping["release"]) == _release_date(mapping_release)
            )
        )

    return ensure_local_db(
        path,
        is_valid=valid,
        build=_build_with_progress,
        consent_message=_CONSENT_MESSAGE.format(path=path),
        auto=auto,
        refresh=refresh,
        min_free_bytes=500_000_000,  # ~53 MB download + build headroom
    )
