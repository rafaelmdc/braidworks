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
import re
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterable, Iterator

# The bundled crosswalk's AGORA2 release — part of the (offline) fingerprint.
CROSSWALK_RELEASE = "AGORA2-v2.01"
_CROSSWALK_FILE = "agora2_crosswalk.tsv"


@lru_cache(maxsize=1)
def load_crosswalk() -> dict[str, list[dict[str, str]]]:
    """``ncbi_taxid -> [{reconstruction_id, gcf_id}, ...]`` from the bundled TSV.

    A taxid may carry several strains (distinct reconstructions), so each maps to a
    list, ordered by ``reconstruction_id`` for determinism.
    """
    raw = (files("agora_weaver") / "data" / _CROSSWALK_FILE).read_text(encoding="utf-8")
    table: dict[str, list[dict[str, str]]] = {}
    for row in csv.DictReader(raw.splitlines(), delimiter="\t"):
        taxid = (row.get("ncbi_taxid") or "").strip()
        microbe_id = (row.get("microbe_id") or "").strip()
        if not taxid or not microbe_id:
            continue
        table.setdefault(taxid, []).append(
            {"reconstruction_id": microbe_id, "gcf_id": (row.get("gcf") or "").strip()}
        )
    for recs in table.values():
        recs.sort(key=lambda r: r["reconstruction_id"])
    return table


def reconstructions_for(taxid: str) -> list[dict[str, str]]:
    """The AGORA2 reconstruction(s) for one NCBI taxid (empty list = miss)."""
    return load_crosswalk().get(str(taxid).strip(), [])


# --- Reaction DB (built by setup.ensure_agora_db) -------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reaction (reconstruction TEXT NOT NULL, abbreviation TEXT NOT NULL,
    PRIMARY KEY (reconstruction, abbreviation));
CREATE TABLE IF NOT EXISTS rxn_info (abbreviation TEXT PRIMARY KEY, subsystem TEXT,
    ec TEXT, kegg TEXT, rhea TEXT);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def open_ro(db_path: str | Path) -> sqlite3.Connection:
    """Open the reaction DB read-only."""
    return sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)


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


def reactions_for(
    con: sqlite3.Connection, reconstruction_ids: Iterable[str]
) -> list[dict[str, Any]]:
    """The reaction repertoire of the given reconstruction(s), enriched + ordered.

    One row per (reconstruction, reaction): ``{reconstruction_id, abbreviation}`` plus
    whichever of ``subsystem/ec/kegg/rhea`` the VMH crosswalk has (empty fields omitted,
    not emitted as null). Ordered by (reconstruction_id, abbreviation).
    """
    out: list[dict[str, Any]] = []
    for rid in reconstruction_ids:
        rows = con.execute(
            """
            SELECT r.abbreviation, i.subsystem, i.ec, i.kegg, i.rhea
            FROM reaction r LEFT JOIN rxn_info i ON i.abbreviation = r.abbreviation
            WHERE r.reconstruction = ? ORDER BY r.abbreviation
            """,
            (rid,),
        ).fetchall()
        for abbrev, subsystem, ec, kegg, rhea in rows:
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
    for _event, elem in ET.iterparse(sbml_bytes_or_stream, events=("end",)):
        tag = elem.tag
        if tag == _RXN_TAG or tag.rsplit("}", 1)[-1] == "reaction":
            rid = elem.get("id") or ""
            if rid.startswith("R_"):
                yield _decode_sbml_id(rid[2:])
            elem.clear()


def build_reaction_db(
    sbml_zip: str | Path,
    rxn_info: Iterable[tuple[str, str | None, str | None, str | None, str | None]],
    db_path: str | Path,
    *,
    content_hash: str,
) -> int:
    """Build the reaction SQLite from the AGORA2 SBML zip + the VMH reaction crosswalk.

    Streams every ``*.xml`` model in ``sbml_zip``, recording (reconstruction, reaction)
    membership; ``rxn_info`` rows are ``(abbreviation, subsystem, ec, kegg, rhea)``.
    Returns the number of membership rows written.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        con.executescript(_SCHEMA)
        con.executemany(
            "INSERT OR REPLACE INTO rxn_info (abbreviation, subsystem, ec, kegg, rhea) "
            "VALUES (?, ?, ?, ?, ?)",
            rxn_info,
        )
        written = 0
        with zipfile.ZipFile(sbml_zip) as zf:
            for name in zf.namelist():
                if not name.endswith(".xml"):
                    continue
                reconstruction = Path(name).stem
                with zf.open(name) as fh:
                    rows = ((reconstruction, abbrev) for abbrev in iter_sbml_reactions(fh))
                    cur = con.executemany(
                        "INSERT OR IGNORE INTO reaction (reconstruction, abbreviation) "
                        "VALUES (?, ?)",
                        rows,
                    )
                    written += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        con.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('content_hash', ?)",
            (content_hash,),
        )
        con.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('release', ?)",
            (CROSSWALK_RELEASE,),
        )
        con.commit()
        return written
    finally:
        con.close()
