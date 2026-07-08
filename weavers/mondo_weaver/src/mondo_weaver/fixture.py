"""A tiny, deterministic MONDO dataset for ``weaverkit verify --strict`` and tests.

Builds a mini SQLite (via the same ``setup.write_db``) from a hand-built is-a chain —
ulcerative colitis → colitis → inflammatory bowel disease → digestive system disorder →
disease (root) — with MeSH and MedDRA xrefs, so the spec's golden runs offline.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from mondo_weaver.setup import _Term, write_db


def _term(mondo_id, name, parents=(), xrefs=(), synonyms=()):
    t = _Term(mondo_id)
    t.name = name
    t.parents = list(parents)
    t.xrefs = list(xrefs)
    t.synonyms = list(synonyms)
    return t


_TERMS = [
    _term(
        "MONDO:0005101",
        "ulcerative colitis",
        parents=["MONDO:0005292"],
        xrefs=[("MESH", "D003093", True), ("MedDRA", "10045365", True)],
        synonyms=["colitis ulcerative"],
    ),
    _term(
        "MONDO:0005292",
        "colitis",
        parents=["MONDO:0005265"],
        xrefs=[("MESH", "D003092", True)],
    ),
    _term(
        "MONDO:0005265",
        "inflammatory bowel disease",
        parents=["MONDO:0004335"],
        xrefs=[("MESH", "D015212", True)],
    ),
    _term(
        "MONDO:0004335",
        "digestive system disorder",
        parents=["MONDO:0000001"],
        xrefs=[("MESH", "D004066", True)],
    ),
    _term("MONDO:0000001", "disease or disorder"),  # root: no parents
]

_cached_path: Path | None = None


def build_fixture_db(target: Path) -> None:
    """Write the mini fixture DB to ``target`` (canned records, no network)."""
    write_db(target, data_version="releases/2020-01-01", terms=_TERMS)


def fixture_db_path() -> Path:
    """Build the fixture DB once per process and return its path."""
    global _cached_path
    if _cached_path is None:
        directory = Path(tempfile.mkdtemp(prefix="mondo_fixture_"))
        _cached_path = directory / "mondo.sqlite"
        build_fixture_db(_cached_path)
    return _cached_path
