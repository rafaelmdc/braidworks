"""ncbi.list_children against a mocked Datasets v2 children endpoint (offline).

Exercises subtree walking, the `rank` parameter, dedup + deterministic order, the
set-output fan dimension (a list of child taxids), count/records, and the misses.
"""

from __future__ import annotations

import httpx

from braidworks.core import Strand, StrandSet, WeaveStatus

from ncbi_weaver import build_ncbi_weaver, vocab

# A tiny subtree for genus 216851: two species + one strain + a "no rank" group node.
SUBTREE = {
    "216851": [
        {"tax_id": 216851, "rank": "GENUS", "current_scientific_name": {"name": "Faecalibacterium"}},
        {"tax_id": 853, "rank": "SPECIES", "current_scientific_name": {"name": "F. prausnitzii"}},
        {"tax_id": 4203190, "rank": "SPECIES", "current_scientific_name": {"name": "F. gallinarum"}},
        {"tax_id": 411485, "rank": "STRAIN", "current_scientific_name": {"name": "F. prausnitzii A2-165"}},
        {"tax_id": 2646395, "rank": "NO_RANK", "current_scientific_name": {"name": "unclassified Faecalibacterium"}},
    ],
    "999999": [],  # a taxid with no subtree
}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if request.method == "GET" and path.endswith("/dataset_report") and "/taxonomy/taxon/" in path:
        taxid = path.split("/taxonomy/taxon/", 1)[1].split("/")[0]
        rows = SUBTREE.get(taxid)
        if rows is None:
            return httpx.Response(404, json={})
        reports = [{"taxonomy": n} for n in rows]
        return httpx.Response(200, json={"reports": reports, "total_count": len(reports)})
    return httpx.Response(404, json={})


def _weaver():
    client = httpx.AsyncClient(
        base_url="https://api.test/datasets/v2", transport=httpx.MockTransport(_handler)
    )
    return build_ncbi_weaver(api_client=client)


async def _children(taxid, *, rank=None):
    params = {"rank": rank} if rank is not None else None
    out = await _weaver().execute_batch(
        vocab.LIST_CHILDREN,
        [StrandSet.from_strands("e", [Strand(vocab.TAXON_ID, taxid)])],
        requested_outputs=vocab.CHILDREN_OUTPUTS,
        backend="api",
        params=params,
    )
    return out[0]


async def test_default_rank_species_returns_species_only():
    r = await _children("216851")  # default rank = species
    assert r.status is WeaveStatus.OK
    sm = {s.type_id: s.value for s in r.strands}
    # the fan dimension: distinct species taxids, ascending (excludes the genus + strain + no_rank)
    assert sm[vocab.TAXON_ID] == [853, 4203190]
    assert sm[vocab.CHILDREN_COUNT] == 2
    assert {c["taxid"] for c in sm[vocab.CHILDREN_RECORDS]} == {853, 4203190}
    assert all(c["rank"] == "species" for c in sm[vocab.CHILDREN_RECORDS])


async def test_rank_param_selects_a_different_rank():
    r = await _children("216851", rank="strain")
    sm = {s.type_id: s.value for s in r.strands}
    assert sm[vocab.TAXON_ID] == [411485]
    assert sm[vocab.CHILDREN_COUNT] == 1


async def test_rank_with_no_matches_is_a_miss():
    r = await _children("216851", rank="family")  # no family-rank descendants
    assert r.status is WeaveStatus.NO_MATCH


async def test_empty_subtree_is_a_miss():
    r = await _children("999999")
    assert r.status is WeaveStatus.NO_MATCH


async def test_unknown_taxid_404_is_a_miss():
    r = await _children("123")  # not in SUBTREE -> 404
    assert r.status is WeaveStatus.NO_MATCH


async def test_set_output_fans_out():
    # ALL policy forks one child per species taxid (the fan dimension).
    from braidworks.core import Braider, BraidRegistry, ExpandPolicy, LocalExecutor

    reg = BraidRegistry()
    reg.register(_weaver())
    braid = Braider(reg).plan(
        available_types=frozenset({vocab.TAXON_ID}),
        target_types=frozenset({vocab.CHILDREN_COUNT}),
    )
    sets = [StrandSet.from_strands("g", [Strand(vocab.TAXON_ID, "216851")])]
    result = await LocalExecutor(reg).execute(braid, sets, expand_policy=ExpandPolicy.all())
    # one leaf per species child, each carrying a single taxid
    assert len(result.resolved) == 2
    assert {ss.get(vocab.TAXON_ID).value for ss in result.resolved} == {853, 4203190}
    assert all(ss.parent_id == "g" for ss in result.resolved)
