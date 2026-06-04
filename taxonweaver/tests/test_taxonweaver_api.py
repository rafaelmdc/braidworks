"""DatasetsV2Backend against a mocked NCBI Datasets v2 transport."""

from __future__ import annotations

import json
from urllib.parse import unquote

import httpx

from braidworks.core import Strand, StrandSet, WeaveStatus

from taxonweaver import build_ncbi_weaver, vocab

EXACT = {
    "Homo sapiens": {
        "tax_id": 9606,
        "organism_name": "Homo sapiens",
        "rank": "species",
        "lineage": [131567, 9605],
    },
}
ANCESTORS = {
    "131567": {"tax_id": 131567, "organism_name": "cellular organisms", "rank": "no rank", "lineage": []},
    "9605": {"tax_id": 9605, "organism_name": "Homo", "rank": "genus", "lineage": [131567]},
}
SUGGEST = {
    "Homo sapeins": [{"sci_name": "Homo sapiens", "tax_id": "9606", "rank": "species"}],
    "Bacterium ambiguum": [
        {"sci_name": "Bacterium alpha", "tax_id": "111", "rank": "species"},
        {"sci_name": "Bacterium beta", "tax_id": "222", "rank": "species"},
    ],
}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if request.method == "POST" and path.endswith("/taxonomy/dataset_report"):
        taxons = json.loads(request.content)["taxons"]
        nodes = []
        for t in taxons:
            node = EXACT.get(t) or ANCESTORS.get(str(t))
            if node is not None:
                nodes.append({"query": [t], "taxonomy": node})
        return httpx.Response(200, json={"taxonomy_nodes": nodes})
    if request.method == "GET" and "/taxonomy/taxon_suggest/" in path:
        name = unquote(path.split("/taxonomy/taxon_suggest/", 1)[1])
        return httpx.Response(200, json={"sci_name_and_ids": SUGGEST.get(name, [])})
    return httpx.Response(404, json={})


def _weaver():
    client = httpx.AsyncClient(
        base_url="https://api.test/datasets/v2", transport=httpx.MockTransport(_handler)
    )
    return build_ncbi_weaver(api_client=client)


def _sm(result):
    return {s.type_id: s.value for s in result.strands}


async def _resolve(weaver, name, outputs):
    out = await weaver.execute_batch(
        vocab.RESOLVE_NAME,
        [StrandSet.from_strands("e", [Strand(vocab.ORGANISM_NAME, name)])],
        requested_outputs=frozenset(outputs),
        backend="api",
    )
    return out[0]


async def test_api_exact_core_only():
    r = await _resolve(_weaver(), "Homo sapiens", {vocab.TAXON_ID})
    assert r.status is WeaveStatus.OK
    sm = _sm(r)
    assert sm[vocab.TAXON_ID] == 9606
    assert sm[vocab.PARENT_ID] == 9605
    assert vocab.LINEAGE not in sm
    assert r.computed_groups == frozenset({"core"})


async def test_api_lineage_resolves_ancestor_names():
    r = await _resolve(_weaver(), "Homo sapiens", {vocab.TAXON_ID, vocab.LINEAGE})
    assert r.status is WeaveStatus.OK
    lineage = _sm(r)[vocab.LINEAGE]
    assert [e["taxid"] for e in lineage] == [131567, 9605, 9606]
    assert lineage[0]["name"] == "cellular organisms"
    assert lineage[-1]["name"] == "Homo sapiens"
    assert r.computed_groups == frozenset({"core", "lineage"})


async def test_api_fuzzy_unique_requires_review():
    r = await _resolve(_weaver(), "Homo sapeins", {vocab.TAXON_ID})
    assert r.status is WeaveStatus.OK
    assert r.requires_review is True
    sm = _sm(r)
    assert sm[vocab.TAXON_ID] == 9606
    assert sm[vocab.TAXON_ID] is not None
    # re-scored confidence is below an exact match
    assert r.strands[0].confidence < 1.0


async def test_api_ambiguous_has_candidates():
    r = await _resolve(_weaver(), "Bacterium ambiguum", {vocab.TAXON_ID})
    assert r.status is WeaveStatus.AMBIGUOUS
    assert len(r.candidates) == 2
    assert r.requires_review is True


async def test_api_no_match():
    r = await _resolve(_weaver(), "Totally unknown organism", {vocab.TAXON_ID})
    assert r.status is WeaveStatus.NO_MATCH


async def test_api_batch_preserves_order():
    w = _weaver()
    sets = [
        StrandSet.from_strands(f"e{i}", [Strand(vocab.ORGANISM_NAME, n)])
        for i, n in enumerate(["Homo sapiens", "Homo sapeins", "Totally unknown organism"])
    ]
    out = await w.execute_batch(
        vocab.RESOLVE_NAME, sets, requested_outputs=frozenset({vocab.TAXON_ID}), backend="api"
    )
    assert [r.status for r in out] == [WeaveStatus.OK, WeaveStatus.OK, WeaveStatus.NO_MATCH]


def test_api_fingerprint():
    assert _weaver().backend_fingerprint("api") == "datasets-v2"
