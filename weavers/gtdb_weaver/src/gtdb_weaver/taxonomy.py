"""Shared GTDB taxonomy logic: parse a ``gtdb_taxonomy`` string and build/query
the local NCBI-taxid → GTDB crosswalk. Used by both backends and by the DB build.

A GTDB taxonomy string is a rank-prefixed, ``;``-joined lineage, e.g.
``d__Bacteria;p__Pseudomonadota;...;g__Escherichia;s__Escherichia coli``
(the live API uses ``; `` with spaces — both are handled).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from braidworks.core.localdb import ensure_local_db
from braidworks.core.sqlite import readonly_uri

# GTDB rank prefix -> canonical rank name (domain..species).
_RANKS = {
    "d": "domain",
    "p": "phylum",
    "c": "class",
    "o": "order",
    "f": "family",
    "g": "genus",
    "s": "species",
}


def parse_gtdb_taxonomy(taxonomy: str) -> tuple[str | None, list[dict[str, str]]]:
    """``gtdb_taxonomy`` string -> (gtdb.taxon.id, lineage).

    ``gtdb.taxon.id`` is the most specific rank-prefixed token (e.g.
    ``s__Escherichia coli``); ``lineage`` is an ordered list of ``{rank, name}``
    from domain to species. Empty/placeholder ranks (``s__``) are skipped.
    """
    lineage: list[dict[str, str]] = []
    taxon_id: str | None = None
    for token in taxonomy.split(";"):
        token = token.strip()
        if "__" not in token:
            continue
        prefix, _, name = token.partition("__")
        rank = _RANKS.get(prefix.strip())
        name = name.strip()
        if not rank or not name:
            continue
        lineage.append({"rank": rank, "name": name})
        taxon_id = token  # most specific seen so far
    return taxon_id, lineage


def _species_name(taxonomy: str) -> str | None:
    """The lowercased GTDB species name (no ``s__``) for the name index, if any."""
    taxon_id, _ = parse_gtdb_taxonomy(taxonomy)
    if taxon_id and taxon_id.startswith("s__"):
        return taxon_id[3:].strip().lower()
    return None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS taxon (ncbi_taxid INTEGER PRIMARY KEY, gtdb_taxonomy TEXT NOT NULL, is_rep INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS species (name TEXT PRIMARY KEY, gtdb_taxonomy TEXT NOT NULL, rep_accession TEXT);
CREATE TABLE IF NOT EXISTS classification (ncbi_taxid INTEGER NOT NULL, gtdb_taxonomy TEXT NOT NULL, is_rep INTEGER NOT NULL, accession TEXT NOT NULL, PRIMARY KEY(ncbi_taxid, gtdb_taxonomy, accession, is_rep));
CREATE TABLE IF NOT EXISTS species_candidate (name TEXT NOT NULL, gtdb_taxonomy TEXT NOT NULL, accession TEXT NOT NULL, PRIMARY KEY(name, gtdb_taxonomy, accession));
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def _build_crosswalk_db(
    rows: Iterable[tuple[int, str, bool, str]], db_path: str | Path, *, release: str
) -> None:
    """Build the crosswalk SQLite from ``(ncbi_taxid, gtdb_taxonomy, is_rep, accession)`` rows.

    Retain every distinct genome classification. Compatibility indexes use stable
    representative/identity ordering, but public lookup rejects competing taxonomies
    rather than presenting that representative as an authoritative crosswalk.
    """
    if not release.strip():
        raise ValueError("GTDB crosswalk requires a nonempty release")
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        con.executescript(_SCHEMA)
        buffer: list[tuple[int, str, bool, str]] = []

        def flush() -> None:
            con.executemany("INSERT OR IGNORE INTO classification VALUES (?, ?, ?, ?)", buffer)
            con.executemany(
                "INSERT OR IGNORE INTO species_candidate VALUES (?, ?, ?)",
                (
                    (name, tax, acc)
                    for _, tax, rep, acc in buffer
                    if rep and (name := _species_name(tax))
                ),
            )
            buffer.clear()

        for taxid, taxonomy, is_rep, accession in rows:
            if taxonomy:
                buffer.append((int(taxid), taxonomy, bool(is_rep), str(accession or "")))
                if len(buffer) == 1000:
                    flush()
        flush()
        if con.execute("SELECT 1 FROM classification LIMIT 1").fetchone() is None:
            raise ValueError("GTDB crosswalk has no usable taxonomy rows")
        # Let SQLite retain and sort source-sized data; Python retains one chunk.
        con.execute(
            "INSERT OR REPLACE INTO taxon "
            "SELECT ncbi_taxid, gtdb_taxonomy, is_rep FROM ("
            "SELECT *, ROW_NUMBER() OVER (PARTITION BY ncbi_taxid "
            "ORDER BY is_rep DESC, gtdb_taxonomy, accession) AS position FROM classification"
            ") WHERE position = 1"
        )
        candidates = con.execute(
            "SELECT gtdb_taxonomy, accession FROM classification WHERE is_rep = 1 "
            "ORDER BY ncbi_taxid, gtdb_taxonomy, accession"
        )
        con.executemany(
            "INSERT OR IGNORE INTO species VALUES (?, ?, ?)",
            ((name, tax, acc) for tax, acc in candidates if (name := _species_name(tax))),
        )
        con.executemany(
            "INSERT OR REPLACE INTO meta VALUES (?, ?)",
            [("schema_version", "2"), ("build_id", uuid.uuid4().hex)],
        )
        con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('release', ?)", (release,))
        con.commit()
    finally:
        con.close()


def open_ro(db_path: str | Path) -> sqlite3.Connection:
    """Open the crosswalk DB read-only."""
    return sqlite3.connect(readonly_uri(db_path), uri=True)


def db_release(db_path: str | Path) -> str | None:
    """The GTDB release recorded in the crosswalk DB, if readable."""
    try:
        con = open_ro(db_path)
    except sqlite3.Error:
        return None
    try:
        row = con.execute("SELECT value FROM meta WHERE key = 'release'").fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None
    finally:
        con.close()


class AmbiguousClassification(ValueError):
    """Observed classifications cannot establish a single GTDB identity."""


def lookup(con: sqlite3.Connection, query: dict[str, Any]) -> str | None:
    """Resolve only a unique classification; retain competing genome evidence."""
    taxid = query.get("ncbi.taxon.id")
    if taxid not in (None, ""):
        try:
            taxid = int(taxid)
        except (ValueError, TypeError):
            return None
        rows = con.execute(
            "SELECT gtdb_taxonomy, accession, is_rep FROM classification "
            "WHERE ncbi_taxid = ? ORDER BY gtdb_taxonomy, accession, is_rep DESC",
            (taxid,),
        ).fetchall()
    else:
        name = query.get("organism.scientific_name")
        rows = con.execute(
            "SELECT gtdb_taxonomy, accession, 1 FROM species_candidate "
            "WHERE name = ? ORDER BY gtdb_taxonomy, accession",
            (str(name or "").strip().lower(),),
        ).fetchall()
    taxonomies = sorted({row[0] for row in rows})
    if len(taxonomies) > 1:
        raise AmbiguousClassification(
            "Conflicting GTDB classifications require review: "
            + json.dumps([list(row) for row in rows])
        )
    return taxonomies[0] if taxonomies else None


def rep_accession(con: sqlite3.Connection, query: dict[str, Any]) -> str | None:
    """Resolve one query to its GTDB species representative genome accession.

    That accession is the organism's leaf label in the GTDB reference tree, so it is
    the join from an input id to :func:`tree.build_rootpaths`. Resolves the query to a
    GTDB taxonomy (:func:`lookup`), then reads the species' representative accession.
    Returns None when the organism is unknown or its species has no recorded accession.
    """
    taxonomy_str = lookup(con, query)
    if not taxonomy_str:
        return None
    species_name = _species_name(taxonomy_str)
    if not species_name:
        return None
    row = con.execute(
        "SELECT rep_accession FROM species WHERE name = ?", (species_name,)
    ).fetchone()
    return row[0] if row and row[0] else None


def crosswalk_is_valid(path: Path) -> bool:
    """Check the complete query schema and required identity, without modifying it."""
    try:
        con = open_ro(path)
    except sqlite3.Error:
        return False
    try:
        con.execute("SELECT ncbi_taxid, gtdb_taxonomy, is_rep FROM taxon LIMIT 0")
        con.execute("SELECT name, gtdb_taxonomy, rep_accession FROM species LIMIT 0")
        con.execute(
            "SELECT ncbi_taxid, gtdb_taxonomy, is_rep, accession FROM classification LIMIT 0"
        )
        con.execute("SELECT name, gtdb_taxonomy, accession FROM species_candidate LIMIT 0")
        metadata = dict(con.execute("SELECT key, value FROM meta"))
        return (
            metadata.get("schema_version") == "2"
            and bool(metadata.get("release"))
            and bool(metadata.get("build_id"))
            and con.execute("SELECT 1 FROM taxon LIMIT 1").fetchone() is not None
            and con.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        )
    except sqlite3.Error:
        return False
    finally:
        con.close()


def build_crosswalk_db(
    rows: Iterable[tuple[int, str, bool, str]], db_path: str | Path, *, release: str
) -> None:
    """Publish a complete validated replacement; preserve the target on failure.

    Explicit local builds reuse the shared staging/lock/publish orchestration;
    consent and large-download disk margins belong to the acquisition entry point.
    """
    ensure_local_db(
        Path(db_path),
        is_valid=crosswalk_is_valid,
        build=lambda staged: _build_crosswalk_db(rows, staged, release=release),
        consent_message="",
        auto=True,
        refresh=True,
        min_free_bytes=0,
    )
