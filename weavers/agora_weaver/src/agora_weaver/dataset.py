"""Shared AGORA2 data access for agora_weaver.

Two data sources, joined at query time:

- **The bundled crosswalk** (``data/agora2_crosswalk.tsv``) — every AGORA2 strain's
  ``ncbi_taxid -> {reconstruction_id, gcf}`` (AGORA2 Supplementary Table S1). Ships in
  the package, so the ``core`` output group works offline for all 7,302 reconstructions.
- **The reaction DB** (a SQLite built by ``setup.ensure_agora_db``) — the per-model
  reaction repertoire parsed from the AGORA2 SBML archive, plus the VMH reaction
  crosswalk (abbreviation -> subsystem/EC/KEGG/Rhea). Heavy, consent-gated; only needed
  for the ``reactions`` group.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
import sqlite3
import uuid
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterable, Iterator, Mapping
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from types import MappingProxyType
from typing import Any

# The AGORA2 SBML archive is compressed with Deflate64 (method 9), which the stdlib
# zipfile cannot decode; importing this monkeypatches zipfile to support it.
import zipfile_deflate64  # noqa: F401
from braidworks.core.localdb import ensure_local_db
from braidworks.core.sqlite import readonly_uri

logger = logging.getLogger("agora_weaver.dataset")

# The bundled crosswalk's AGORA2 release — part of the (offline) fingerprint.
CROSSWALK_RELEASE = "AGORA2-v2.01"
_CROSSWALK_FILE = "agora2_crosswalk.tsv"


@lru_cache(maxsize=1)
def _crosswalk_index() -> Mapping[str, tuple[tuple[str, str], ...]]:
    """Immutable source index; callers receive detached projections."""
    raw = (files("agora_weaver") / "data" / _CROSSWALK_FILE).read_text(encoding="utf-8")
    table: dict[str, list[tuple[str, str]]] = {}
    for row in csv.DictReader(raw.splitlines(), delimiter="\t"):
        taxid = (row.get("ncbi_taxid") or "").strip()
        microbe_id = (row.get("microbe_id") or "").strip()
        if taxid and microbe_id:
            table.setdefault(taxid, []).append((microbe_id, (row.get("gcf") or "").strip()))
    return MappingProxyType({key: tuple(sorted(rows)) for key, rows in table.items()})


def reconstructions_for(taxid: str) -> list[dict[str, str]]:
    """Detached, deterministically ordered reconstructions for one taxid."""
    return [
        {"reconstruction_id": rid, "gcf_id": gcf}
        for rid, gcf in _crosswalk_index().get(str(taxid).strip(), ())
    ]


def load_crosswalk() -> dict[str, list[dict[str, str]]]:
    """Return a detached full crosswalk; single-taxid queries use the private index."""
    return {taxid: reconstructions_for(taxid) for taxid in _crosswalk_index()}


# --- Reaction DB (built by setup.ensure_agora_db) -------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reaction (reconstruction TEXT NOT NULL, abbreviation TEXT NOT NULL,
    PRIMARY KEY (reconstruction, abbreviation));
CREATE TABLE IF NOT EXISTS rxn_info (abbreviation TEXT PRIMARY KEY, subsystem TEXT,
    ec TEXT, kegg TEXT, rhea TEXT);
CREATE TABLE IF NOT EXISTS model_coverage (reconstruction TEXT PRIMARY KEY,
    status TEXT NOT NULL, reaction_count INTEGER NOT NULL, source_member TEXT NOT NULL,
    error TEXT);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def open_ro(db_path: str | Path) -> sqlite3.Connection:
    """Open the reaction DB read-only."""
    return sqlite3.connect(readonly_uri(db_path), uri=True)


def db_content_hash(db_path: str | Path) -> str | None:
    """The content hash recorded when the reaction DB was built, if readable."""
    try:
        con = open_ro(db_path)
    except sqlite3.Error:
        return None
    try:
        row = con.execute("SELECT value FROM meta WHERE key = 'content_hash'").fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None
    finally:
        con.close()


class IncompleteModelCoverage(ValueError):
    """The acquisition manifest cannot establish a model repertoire."""


def reactions_for(
    con: sqlite3.Connection, reconstruction_ids: Iterable[str]
) -> list[dict[str, Any]]:
    """The reaction repertoire of the given reconstruction(s), enriched + ordered.

    One row per (reconstruction, reaction): ``{reconstruction_id, abbreviation}`` plus
    whichever of ``subsystem/ec/kegg/rhea`` the VMH crosswalk has (empty fields omitted,
    not emitted as null). Ordered by (reconstruction_id, abbreviation).
    """
    out: list[dict[str, Any]] = []
    ids = sorted(set(reconstruction_ids))
    # Stay below SQLite's conservative parameter limit and bound intermediate rows.
    for start in range(0, len(ids), 250):
        chunk = ids[start : start + 250]
        placeholders = ",".join("?" for _ in chunk)
        coverage = {
            rid: (status, error)
            for rid, status, error in con.execute(
                f"SELECT reconstruction, status, error FROM model_coverage "
                f"WHERE reconstruction IN ({placeholders})",
                chunk,
            )
        }
        for rid in chunk:
            status, reason = coverage.get(rid, (None, "model not acquired"))
            if status != "processed":
                raise IncompleteModelCoverage(
                    f"reaction repertoire unavailable for {rid}: {reason}"
                )
        rows = con.execute(
            "SELECT r.reconstruction, r.abbreviation, i.subsystem, i.ec, i.kegg, i.rhea "
            "FROM reaction r LEFT JOIN rxn_info i ON i.abbreviation = r.abbreviation "
            f"WHERE r.reconstruction IN ({placeholders}) "
            "ORDER BY r.reconstruction, r.abbreviation",
            chunk,
        )
        for rid, abbrev, subsystem, ec, kegg, rhea in rows:
            rec: dict[str, Any] = {"reconstruction_id": rid, "abbreviation": abbrev}
            for key, val in (("subsystem", subsystem), ("ec", ec), ("kegg", kegg), ("rhea", rhea)):
                if val:
                    rec[key] = val
            out.append(rec)
    return out


# --- SBML parsing / build -------------------------------------------------------

# SBML reaction ids are prefixed 'R_'; the remainder is the VMH abbreviation.
_RXN_TAG = "{http://www.sbml.org/sbml/level3/version1/core}reaction"
# libSBML encodes non-alphanumerics as '__<ascii>__' (e.g. '(' -> '__40__'); decode
# back to the canonical VMH abbreviation so exchange/transport ids join the crosswalk.
_SBML_CODE = re.compile(r"__(\d+)__")


def _decode_sbml_id(sid: str) -> str:
    """Decode libSBML ``__<ascii>__`` escapes to the canonical VMH abbreviation."""
    return _SBML_CODE.sub(lambda m: chr(int(m.group(1))), sid)


def iter_sbml_reactions(sbml_bytes_or_stream: Any) -> Iterator[str]:
    """Yield VMH reaction abbreviations (``R_`` stripped, SBML-decoded) from one SBML stream.

    Streams with ``iterparse`` and clears elements, so an 8 MB model never fully
    materialises. Tolerant of namespaced or bare ``<reaction>`` tags.
    """
    parents: list[ET.Element] = []
    has_model = False
    for event, elem in ET.iterparse(sbml_bytes_or_stream, events=("start", "end")):
        if event == "start":
            local_tag = elem.tag.rsplit("}", 1)[-1]
            if not parents and local_tag != "sbml":
                raise ET.ParseError("expected SBML root element")
            has_model = has_model or local_tag == "model"
            parents.append(elem)
            continue
        tag = elem.tag
        if tag == _RXN_TAG or tag.rsplit("}", 1)[-1] == "reaction":
            rid = elem.get("id") or ""
            if rid.startswith("R_"):
                yield _decode_sbml_id(rid[2:])
        parents.pop()
        if parents:
            parents[-1].remove(elem)
        elem.clear()
    if not has_model:
        raise ET.ParseError("SBML model element missing")


def _build_reaction_db(
    sbml_zip: str | Path,
    rxn_info: Iterable[tuple[str, str | None, str | None, str | None, str | None]],
    db_path: str | Path,
    *,
    content_hash: str,
    annotation_source: str | None = None,
    sbml_source: str | None = None,
) -> int:
    """Build the reaction SQLite from the AGORA2 SBML zip + the VMH reaction crosswalk.

    Streams every ``*.xml`` model in ``sbml_zip``, recording (reconstruction, reaction)
    membership; ``rxn_info`` rows are ``(abbreviation, subsystem, ec, kegg, rhea)``.
    Returns the number of membership rows written.
    """
    if not content_hash.strip():
        raise ValueError("AGORA reaction build requires a nonempty source content hash")
    annotation_digest = hashlib.sha256()
    annotation_count = 0

    def annotated_rows():
        nonlocal annotation_count
        for row in rxn_info:
            annotation_digest.update(json.dumps(row, separators=(",", ":")).encode())
            annotation_digest.update(b"\n")
            annotation_count += 1
            yield row

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        con.executescript(_SCHEMA)
        con.executemany(
            "INSERT OR REPLACE INTO rxn_info (abbreviation, subsystem, ec, kegg, rhea) "
            "VALUES (?, ?, ?, ?, ?)",
            annotated_rows(),
        )
        written = 0
        skipped = 0
        processed = 0
        with zipfile.ZipFile(sbml_zip) as zf:
            for name in zf.namelist():
                if not name.endswith(".xml"):
                    continue
                reconstruction = Path(name).stem
                try:
                    with zf.open(name) as fh:
                        # Materialize per model so a malformed one is skipped, not fatal — a
                        # multi-thousand-model archive can carry the odd corrupt SBML file.
                        rows = [(reconstruction, abbrev) for abbrev in iter_sbml_reactions(fh)]
                except ET.ParseError as exc:
                    logger.warning("skipping malformed SBML model %s: %s", name, exc)
                    skipped += 1
                    con.execute(
                        "INSERT INTO model_coverage VALUES (?, ?, ?, ?, ?)",
                        (reconstruction, "skipped", 0, name, str(exc)),
                    )
                    continue
                processed += 1
                con.execute(
                    "INSERT INTO model_coverage VALUES (?, ?, ?, ?, ?)",
                    (reconstruction, "processed", len(set(rows)), name, None),
                )
                cur = con.executemany(
                    "INSERT OR IGNORE INTO reaction (reconstruction, abbreviation) VALUES (?, ?)",
                    rows,
                )
                written += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        if written == 0:
            raise ValueError("no reactions parsed from the AGORA2 SBML archive")
        if skipped:
            logger.warning("skipped %d malformed SBML model(s) of the archive", skipped)
        con.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('content_hash', ?)",
            (content_hash,),
        )
        con.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('release', ?)",
            (CROSSWALK_RELEASE,),
        )
        con.executemany(
            "INSERT OR REPLACE INTO meta VALUES (?, ?)",
            [
                ("schema_version", "2"),
                ("models_processed", str(processed)),
                ("models_skipped", str(skipped)),
                ("build_id", uuid.uuid4().hex),
                ("annotation_sha256", annotation_digest.hexdigest()),
                ("annotation_rows", str(annotation_count)),
                ("annotation_source", annotation_source or "caller-supplied"),
                ("sbml_source", sbml_source or str(sbml_zip)),
                ("annotation_hash_encoding", "ordered-json-rows-v1"),
            ],
        )
        con.commit()
        return written
    finally:
        con.close()


def reaction_db_is_valid(path: Path) -> bool:
    """Validate the complete reaction query schema and source identity."""
    try:
        con = open_ro(path)
    except sqlite3.Error:
        return False
    try:
        con.execute("SELECT reconstruction, abbreviation FROM reaction LIMIT 0")
        con.execute("SELECT abbreviation, subsystem, ec, kegg, rhea FROM rxn_info LIMIT 0")
        con.execute(
            "SELECT reconstruction, status, reaction_count, source_member, error "
            "FROM model_coverage LIMIT 0"
        )
        metadata = dict(con.execute("SELECT key, value FROM meta"))
        return (
            bool(metadata.get("content_hash"))
            and con.execute("SELECT 1 FROM reaction LIMIT 1").fetchone() is not None
            and con.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        )
    except sqlite3.Error:
        return False
    finally:
        con.close()


def build_reaction_db(
    sbml_zip: str | Path,
    rxn_info: Iterable[tuple[str, str | None, str | None, str | None, str | None]],
    db_path: str | Path,
    *,
    content_hash: str,
    annotation_source: str | None = None,
    sbml_source: str | None = None,
) -> int:
    """Stage, validate and publish a complete replacement, preserving targets on failure.

    Records the archive identity and digest/count/source of the ingested annotation
    rows. Missing source URLs are explicitly identified as caller-supplied/local.
    """
    written = 0

    def build(staged: Path) -> None:
        nonlocal written
        written = _build_reaction_db(
            sbml_zip,
            rxn_info,
            staged,
            content_hash=content_hash,
            annotation_source=annotation_source,
            sbml_source=sbml_source,
        )

    ensure_local_db(
        Path(db_path),
        is_valid=reaction_db_is_valid,
        build=build,
        consent_message="",
        auto=True,
        refresh=True,
        min_free_bytes=0,
    )
    return written
