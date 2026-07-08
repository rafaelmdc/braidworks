"""Behavior tests for the mondo local backend (against the fixture DB)."""

from __future__ import annotations

from braidworks.core import Strand, StrandSet, WeaveStatus

from mondo_weaver.factory import build_mondo_weaver_fixture

MONDO_ID = "disease.mondo.id"
NAME = "disease.ontology.name"
PARENTS = "disease.ontology.parents"
DEPTH = "disease.ontology.depth"
ANCESTORS = "disease.ontology.ancestors"


def _ss(type_id, value):
    return StrandSet.from_strands("e", [Strand(type_id, value)])


async def _resolve(cap, type_id, value, outputs):
    weaver = build_mondo_weaver_fixture()
    out = await weaver.execute_batch(
        cap, [_ss(type_id, value)], requested_outputs=frozenset(outputs), backend="local"
    )
    return out[0]


def _strands(result):
    return {s.type_id: s.value for s in result.strands}


async def test_mesh_resolves_to_mondo_term():
    r = await _resolve(
        "mondo.lookup_by_mesh", "disease.mesh.id", "D003093", {MONDO_ID, NAME, DEPTH}
    )
    assert r.status is WeaveStatus.OK
    sm = _strands(r)
    assert sm[MONDO_ID] == "MONDO:0005101"
    assert sm[NAME] == "ulcerative colitis"
    # UC -> colitis -> IBD -> digestive -> root : 4 hops to the root
    assert sm[DEPTH] == 4
    assert ANCESTORS not in sm  # heavy slice not requested


async def test_ancestor_lineage_is_the_full_isa_chain():
    r = await _resolve("mondo.lookup_by_mesh", "disease.mesh.id", "D003093", {ANCESTORS})
    ids = [a["mondo_id"] for a in _strands(r)[ANCESTORS]]
    # the term itself plus every is-a ancestor up to the root, nearest-first
    assert ids == [
        "MONDO:0005101",
        "MONDO:0005292",
        "MONDO:0005265",
        "MONDO:0004335",
        "MONDO:0000001",
    ]


async def test_direct_parents_only():
    r = await _resolve("mondo.lookup_by_mesh", "disease.mesh.id", "D003093", {PARENTS})
    parents = _strands(r)[PARENTS]
    assert [p["mondo_id"] for p in parents] == ["MONDO:0005292"]
    assert parents[0]["name"] == "colitis"


async def test_meddra_entry_resolves_same_term():
    r = await _resolve("mondo.lookup_by_meddra", "disease.meddra.id", "10045365", {MONDO_ID, NAME})
    sm = _strands(r)
    assert sm[MONDO_ID] == "MONDO:0005101"
    assert sm[NAME] == "ulcerative colitis"


async def test_integer_meddra_id_is_accepted():
    r = await _resolve("mondo.lookup_by_meddra", "disease.meddra.id", 10045365, {MONDO_ID})
    assert _strands(r)[MONDO_ID] == "MONDO:0005101"


async def test_name_lookup_resolves_by_label():
    r = await _resolve(
        "mondo.lookup_by_name", "disease.name", "Ulcerative Colitis", {MONDO_ID, NAME}
    )
    sm = _strands(r)
    assert sm[MONDO_ID] == "MONDO:0005101"  # case/whitespace-insensitive
    assert sm[NAME] == "ulcerative colitis"


async def test_name_lookup_resolves_by_exact_synonym():
    r = await _resolve("mondo.lookup_by_name", "disease.name", "colitis ulcerative", {MONDO_ID})
    assert _strands(r)[MONDO_ID] == "MONDO:0005101"


async def test_unknown_name_is_no_match():
    r = await _resolve("mondo.lookup_by_name", "disease.name", "not a real disease", {NAME})
    assert r.status is WeaveStatus.NO_MATCH


async def test_unknown_disease_is_no_match_not_error():
    r = await _resolve("mondo.lookup_by_mesh", "disease.mesh.id", "D999999", {NAME})
    assert r.status is WeaveStatus.NO_MATCH
