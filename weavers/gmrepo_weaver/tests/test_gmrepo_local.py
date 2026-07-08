"""Behavior tests for the gmrepo local backend (against the fixture DB)."""

from __future__ import annotations

from braidworks.core import Strand, StrandSet, WeaveStatus

from gmrepo_weaver.factory import build_gmrepo_weaver_fixture

CAP = "gmrepo.list_abundances"
OVERVIEW = "microbe.abundance.overview"
NAMES = "microbe.abundance.phenotype_names"
COUNT = "microbe.abundance.count"
ASSOCIATIONS = "microbe.abundance.associations"
RECORDS = "microbe.abundance.records"


def _ss(taxid):
    return StrandSet.from_strands("e", [Strand("ncbi.taxon.id", taxid)])


async def _resolve(weaver, taxid, outputs):
    out = await weaver.execute_batch(
        CAP, [_ss(taxid)], requested_outputs=frozenset(outputs), backend="local"
    )
    return out[0]


def _strands(result):
    return {s.type_id: s.value for s in result.strands}


async def test_summary_slice_is_light():
    r = await _resolve(build_gmrepo_weaver_fixture(), 816, {OVERVIEW, NAMES, COUNT})
    assert r.status is WeaveStatus.OK
    sm = _strands(r)
    assert sm[NAMES] == ["Colitis, Ulcerative"]
    assert sm[COUNT] == 1
    assert sm[OVERVIEW]["name"] == "Bacteroides"
    assert sm[OVERVIEW]["pct_of_all_samples"] == 81.07
    # the light slice must NOT carry the heavy outputs
    assert ASSOCIATIONS not in sm and RECORDS not in sm
    assert r.computed_groups == frozenset({"summary"})


async def test_associations_slice_carries_abundance_signal():
    r = await _resolve(build_gmrepo_weaver_fixture(), 216851, {ASSOCIATIONS})
    rows = {row["phenotype"]: row for row in _strands(r)[ASSOCIATIONS]}
    assert set(rows) == {"Colitis, Ulcerative", "Crohn Disease"}
    uc = rows["Colitis, Ulcerative"]
    assert uc["prevalence_percentage"] == 78.9
    assert uc["abundance_median"] == 2.03
    assert uc["rank"] == "genus"
    assert r.computed_groups == frozenset({"associations"})


async def test_full_blob_has_overview_and_every_row():
    r = await _resolve(build_gmrepo_weaver_fixture(), 216851, {RECORDS})
    blob = _strands(r)[RECORDS]
    assert blob["overview"]["name"] == "Faecalibacterium"
    assert len(blob["associations"]) == 2
    assert {row["mesh_id"] for row in blob["associations"]} == {"D003093", "D003424"}


async def test_unknown_taxid_is_no_match_not_error():
    r = await _resolve(build_gmrepo_weaver_fixture(), 999999999, {NAMES})
    assert r.status is WeaveStatus.NO_MATCH
