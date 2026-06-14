"""Behavior tests for the disbiome local backend (against the fixture DB)."""

from __future__ import annotations

from braidworks.core import Strand, StrandSet, WeaveStatus

from disbiome_weaver.factory import build_disbiome_weaver_fixture

CAP = "disbiome.list_diseases"
NAMES = "microbe.disease.names"
COUNT = "microbe.disease.count"
ASSOCIATIONS = "microbe.disease.associations"
RECORDS = "microbe.disease.records"


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
    r = await _resolve(build_disbiome_weaver_fixture(), 1591, {NAMES, COUNT})
    assert r.status is WeaveStatus.OK
    sm = _strands(r)
    assert sm[NAMES] == ["Autism"]
    assert sm[COUNT] == 1
    # the light slice must NOT carry the heavy outputs
    assert ASSOCIATIONS not in sm and RECORDS not in sm
    assert r.computed_groups == frozenset({"summary"})


async def test_associations_slice():
    r = await _resolve(build_disbiome_weaver_fixture(), 1591, {ASSOCIATIONS})
    row = _strands(r)[ASSOCIATIONS][0]
    assert row["disease_name"] == "Autism"
    assert row["direction"] == "Elevated"
    assert row["method"] == "qPCR"
    assert row["sample"] == "Faeces"
    assert r.computed_groups == frozenset({"associations"})


async def test_full_blob_has_every_joined_field():
    r = await _resolve(build_disbiome_weaver_fixture(), 1591, {RECORDS})
    rec = _strands(r)[RECORDS][0]
    # experiment-level
    assert rec["qualitative_outcome"] == "Elevated"
    assert rec["host_type"] == "Human"
    # joined disease / organism / publication, each complete
    assert rec["disease"]["name"] == "Autism"
    assert rec["organism"]["scientific_name"] == "Lactobacillus"
    assert rec["organism"]["silva_accession_number_base"] == "AATA01000092"
    assert rec["publication"]["first_author"] == "Tomova A"
    assert rec["publication"]["age_of_subjects_given"] == "y"  # a study-quality flag
    # Disbiome's "None" strings are normalized away (experiment- and publication-level)
    assert rec["subject_value"] is None
    assert rec["publication"]["doi"] is None


async def test_multiple_experiments_dedup_names_but_count_all():
    # taxid 1350 has two experiments, both for Crohn's disease.
    r = await _resolve(build_disbiome_weaver_fixture(), 1350, {NAMES, COUNT, ASSOCIATIONS})
    sm = _strands(r)
    assert sm[NAMES] == ["Crohn's disease"]  # de-duplicated
    assert sm[COUNT] == 2  # both experiments counted
    directions = sorted(a["direction"] for a in sm[ASSOCIATIONS])
    assert directions == ["Elevated", "Reduced"]


async def test_miss_is_no_match_not_error():
    r = await _resolve(build_disbiome_weaver_fixture(), 562, {NAMES})
    assert r.status is WeaveStatus.NO_MATCH
    assert r.strands == ()


async def test_non_integer_taxid_misses_cleanly():
    r = await _resolve(build_disbiome_weaver_fixture(), "not-a-taxid", {NAMES})
    assert r.status is WeaveStatus.NO_MATCH


async def test_string_taxid_resolves_like_int():
    r = await _resolve(build_disbiome_weaver_fixture(), "1591", {COUNT})
    assert _strands(r)[COUNT] == 1
