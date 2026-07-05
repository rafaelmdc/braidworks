"""Shared GTDB taxonomy logic: parse a ``gtdb_taxonomy`` string and build/query
the local NCBI-taxid → GTDB crosswalk. Used by both backends and by the DB build.

A GTDB taxonomy string is a rank-prefixed, ``;``-joined lineage, e.g.
``d__Bacteria;p__Pseudomonadota;...;g__Escherichia;s__Escherichia coli``
(the live API uses ``; `` with spaces — both are handled).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable

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
CREATE TABLE IF NOT EXISTS species (name TEXT PRIMARY KEY, gtdb_taxonomy TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def build_crosswalk_db(
    rows: Iterable[tuple[int, str, bool]], db_path: str | Path, *, release: str
) -> None:
    """Build the crosswalk SQLite from ``(ncbi_taxid, gtdb_taxonomy, is_rep)`` rows.

    One taxonomy per ncbi_taxid (representative rows win over non-rep, else first
    seen — deterministic, never trusting row order for the tiebreak). The species
    index is keyed by lowercased GTDB species name from representative rows.
    """
    best: dict[int, tuple[str, bool]] = {}
    species: dict[str, str] = {}
    for taxid, taxonomy, is_rep in rows:
        if not taxonomy:
            continue
        prev = best.get(taxid)
        if prev is None or (is_rep and not prev[1]):
            best[taxid] = (taxonomy, is_rep)
        if is_rep:
            name = _species_name(taxonomy)
            if name and name not in species:
                species[name] = taxonomy

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        con.executescript(_SCHEMA)
        con.executemany(
            "INSERT OR REPLACE INTO taxon (ncbi_taxid, gtdb_taxonomy, is_rep) VALUES (?, ?, ?)",
            ((t, tax, int(rep)) for t, (tax, rep) in best.items()),
        )
        con.executemany(
            "INSERT OR REPLACE INTO species (name, gtdb_taxonomy) VALUES (?, ?)",
            species.items(),
        )
        con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('release', ?)", (release,))
        con.commit()
    finally:
        con.close()


def open_ro(db_path: str | Path) -> sqlite3.Connection:
    """Open the crosswalk DB read-only."""
    return sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)


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


def lookup(con: sqlite3.Connection, query: dict[str, Any]) -> str | None:
    """Resolve one query strand-map to a GTDB taxonomy string, or None.

    Dispatches on the present input: NCBI taxid (authoritative crosswalk) first,
    else GTDB species name (case-insensitive).
    """
    taxid = query.get("ncbi.taxon.id")
    if taxid not in (None, ""):
        try:
            row = con.execute(
                "SELECT gtdb_taxonomy FROM taxon WHERE ncbi_taxid = ?", (int(taxid),)
            ).fetchone()
        except (ValueError, TypeError):
            row = None
        if row:
            return row[0]
    name = query.get("organism.scientific_name")
    if name:
        row = con.execute(
            "SELECT gtdb_taxonomy FROM species WHERE name = ?", (str(name).strip().lower(),)
        ).fetchone()
        if row:
            return row[0]
    return None
