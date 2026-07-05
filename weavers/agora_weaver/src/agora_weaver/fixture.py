"""A tiny, deterministic reaction DB for offline tests/goldens.

The ``core`` group already runs offline (the crosswalk is bundled), but the
``reactions`` group needs a reaction SQLite. Rather than ship or download the 2.17 GB
SBML archive, this builds a minimal reaction DB in a temp dir holding a couple of
**real** reactions from one AGORA2 model (*Abiotrophia defectiva* ATCC 49176) with
their real VMH crosswalk annotations — enough for ``build_agora_weaver_fixture`` to
exercise the repertoire path in ``verify --strict``.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from agora_weaver import dataset

_FIXTURE_RECON = "Abiotrophia_defectiva_ATCC_49176"
# (abbreviation, subsystem, ec, kegg, rhea) — verified against the live VMH API and
# confirmed present in this model's AGORA2 SBML.
_FIXTURE_REACTIONS = [
    ("23DHMPO", "Valine, leucine, and isoleucine metabolism", "1.1.1.86", None, None),
    ("26DAPLLAT", "Lysine metabolism", "2.6.1.83", None, None),
]

# Process-lifetime cache so repeated fixture builds in one run don't rebuild the DB.
_FIXTURE_DB: Path | None = None


def fixture_reaction_db_path() -> Path:
    """Build (once per process) the tiny reaction SQLite and return its path."""
    global _FIXTURE_DB
    if _FIXTURE_DB is not None and _FIXTURE_DB.exists():
        return _FIXTURE_DB
    target = Path(tempfile.mkdtemp(prefix="agora_weaver-fixture-")) / "reactions.sqlite"
    con = sqlite3.connect(target)
    try:
        con.executescript(dataset._SCHEMA)
        con.executemany(
            "INSERT OR REPLACE INTO rxn_info (abbreviation, subsystem, ec, kegg, rhea) "
            "VALUES (?, ?, ?, ?, ?)",
            _FIXTURE_REACTIONS,
        )
        con.executemany(
            "INSERT OR IGNORE INTO reaction (reconstruction, abbreviation) VALUES (?, ?)",
            [(_FIXTURE_RECON, r[0]) for r in _FIXTURE_REACTIONS],
        )
        con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('content_hash', 'fixture')")
        con.commit()
    finally:
        con.close()
    _FIXTURE_DB = target
    return target
