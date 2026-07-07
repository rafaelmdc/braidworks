"""iter_associations — the bulk (whole-table) view an ingestion consumes."""

from __future__ import annotations

from disbiome_weaver import iter_associations
from disbiome_weaver.fixture import fixture_db_path


def _records():
    # A valid db_path short-circuits ensure_disbiome_db, so no network is touched.
    return list(iter_associations(db_path=fixture_db_path()))


def test_yields_every_association_with_a_taxid():
    records = _records()
    assert len(records) == 3
    assert all(isinstance(r["taxid"], int) for r in records)


def test_carries_the_association_signal():
    by_taxid: dict[int, list] = {}
    for r in _records():
        by_taxid.setdefault(r["taxid"], []).append(r)

    autism = by_taxid[1591][0]  # Lactobacillus
    assert autism["disease_name"] == "Autism"
    assert autism["meddra_id"] == "10080683"
    assert autism["outcome"] == "Elevated"

    # Enterococcus (1350) has Crohn's in both directions.
    crohns = by_taxid[1350]
    assert {r["outcome"] for r in crohns} == {"Elevated", "Reduced"}
    assert all(r["meddra_id"] == "10011401" for r in crohns)
