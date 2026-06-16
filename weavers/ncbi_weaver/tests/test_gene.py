"""ncbi gene capabilities (resolve_gene / describe_gene / list_orthologs) — offline.

httpx.MockTransport. Exercises symbol+taxon -> gene id, the summary/products groups
(products fetched only when asked), and orthologs (set-output fan, excludes the query
gene, taxon_filter).
"""

from __future__ import annotations

import httpx

from braidworks.core import Strand, StrandSet, WeaveStatus

from ncbi_weaver import build_ncbi_weaver, vocab

GENES = {
    ("TP53", "9606"): {"gene_id": 7157, "symbol": "TP53", "description": "tumor protein p53",
                       "type": "PROTEIN_CODING", "taxname": "Homo sapiens", "chromosomes": ["17"],
                       "transcript_count": 26, "protein_count": 18},
    ("Trp53", "10090"): {"gene_id": 22059, "symbol": "Trp53",
                         "description": "transformation related protein 53",
                         "type": "PROTEIN_CODING", "taxname": "Mus musculus"},
    ("Tp53", "10116"): {"gene_id": 24842, "symbol": "Tp53", "description": "tumor protein p53",
                        "type": "PROTEIN_CODING", "taxname": "Rattus norvegicus"},
}
ORTHOLOGS = {
    "7157": [
        {"gene_id": 7157, "symbol": "TP53", "taxname": "Homo sapiens"},   # the query gene itself
        {"gene_id": 22059, "symbol": "Trp53", "taxname": "Mus musculus"},
        {"gene_id": 24842, "symbol": "Tp53", "taxname": "Rattus norvegicus"},
    ],
}
PRODUCTS = {
    "7157": [{"product": {"transcripts": [
        {"accession_version": "NM_000546.6", "name": "variant 1",
         "protein": {"accession_version": "NP_000537.3", "name": "cellular tumor antigen p53"}},
    ]}}],
}


def _handler(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls.append(path)
        if "/gene/symbol/" in path and "/taxon/" in path and path.endswith("/dataset_report"):
            rest = path.split("/gene/symbol/", 1)[1]
            symbols = rest.split("/")[0].split(",")
            taxon = rest.split("/taxon/")[1].split("/")[0]
            reports = [{"gene": g, "query": [sym]}
                       for sym in symbols if (g := GENES.get((sym, taxon)))]
            return httpx.Response(200, json={"reports": reports})
        if "/gene/id/" in path and path.endswith("/dataset_report"):
            ids = path.split("/gene/id/", 1)[1].split("/")[0].split(",")
            reports = [
                {"gene": g}
                for gid in ids
                if (g := next((v for (s, t), v in GENES.items()
                               if str(v["gene_id"]) == gid), None))
            ]
            return httpx.Response(200, json={"reports": reports})
        if "/gene/id/" in path and path.endswith("/orthologs"):
            gid = path.split("/gene/id/", 1)[1].split("/")[0]
            rows = ORTHOLOGS.get(gid, [])
            tf = request.url.params.get("taxon_filter")
            if tf == "10090":  # mouse only, for the filter test
                rows = [r for r in rows if r["taxname"] == "Mus musculus"]
            return httpx.Response(200, json={"reports": [{"gene": g} for g in rows]})
        if "/gene/id/" in path and path.endswith("/product_report"):
            gid = path.split("/gene/id/", 1)[1].split("/")[0]
            return httpx.Response(200, json={"reports": PRODUCTS.get(gid, [])})
        return httpx.Response(404, json={})
    return handler


def _weaver(calls):
    client = httpx.AsyncClient(
        base_url="https://api.test/datasets/v2", transport=httpx.MockTransport(_handler(calls))
    )
    return build_ncbi_weaver(api_client=client)


async def _run(cap, type_id, value, outputs, *, params=None, calls=None):
    calls = calls if calls is not None else []
    out = await _weaver(calls).execute_batch(
        cap, [StrandSet.from_strands("e", [Strand(type_id, value)])],
        requested_outputs=frozenset(outputs), backend="api", params=params,
    )
    return out[0], calls


async def test_resolve_gene_symbol_to_id_default_human():
    r, _ = await _run(vocab.RESOLVE_GENE, vocab.PROTEIN_QUERY, "TP53", vocab.RESOLVE_GENE_OUTPUTS)
    assert r.status is WeaveStatus.OK
    sm = {s.type_id: s.value for s in r.strands}
    assert sm[vocab.GENE_ID] == 7157 and isinstance(sm[vocab.GENE_ID], int)
    assert sm[vocab.GENE_SYMBOL] == "TP53" and sm[vocab.GENE_ORGANISM] == "Homo sapiens"


async def test_resolve_gene_batches_many_into_one_request():
    """N symbols (same taxon) -> a single multi-symbol dataset_report request."""
    calls: list[str] = []
    sets = [StrandSet.from_strands(s, [Strand(vocab.PROTEIN_QUERY, s)]) for s in ("TP53", "NOPE")]
    out = await _weaver(calls).execute_batch(
        vocab.RESOLVE_GENE, sets, requested_outputs=frozenset(vocab.RESOLVE_GENE_OUTPUTS),
        backend="api", params={"taxon": "9606"},
    )
    assert out[0].status is WeaveStatus.OK and out[1].status is WeaveStatus.NO_MATCH
    assert {s.type_id: s.value for s in out[0].strands}[vocab.GENE_ID] == 7157
    reports = [p for p in calls if p.endswith("/dataset_report")]
    assert len(reports) == 1  # one bulk request for both symbols


async def test_resolve_gene_unknown_is_a_miss():
    r, _ = await _run(vocab.RESOLVE_GENE, vocab.PROTEIN_QUERY, "NOPE", vocab.RESOLVE_GENE_OUTPUTS)
    assert r.status is WeaveStatus.NO_MATCH


async def test_describe_gene_summary_skips_products_call():
    r, calls = await _run(vocab.DESCRIBE_GENE, vocab.GENE_ID, "7157", vocab.GENE_SUMMARY_GROUP)
    sm = {s.type_id: s.value for s in r.strands}
    assert sm[vocab.GENE_TYPE] == "PROTEIN_CODING"
    assert sm[vocab.GENE_DETAIL]["protein_count"] == 18
    assert vocab.GENE_PRODUCTS not in sm
    assert not any(p.endswith("/product_report") for p in calls)


async def test_describe_gene_products_group_fetches_products():
    r, calls = await _run(vocab.DESCRIBE_GENE, vocab.GENE_ID, "7157",
                          frozenset({vocab.GENE_PRODUCTS}))
    sm = {s.type_id: s.value for s in r.strands}
    assert sm[vocab.GENE_PRODUCTS][0]["protein"] == "NP_000537.3"
    assert any(p.endswith("/product_report") for p in calls)


async def test_describe_gene_batches_many_into_one_request():
    """N gene ids -> a single multi-id dataset_report request, not one per gene."""
    calls: list[str] = []
    sets = [StrandSet.from_strands(str(g), [Strand(vocab.GENE_ID, g)])
            for g in (7157, 22059, 24842)]
    out = await _weaver(calls).execute_batch(
        vocab.DESCRIBE_GENE, sets,
        requested_outputs=frozenset(vocab.GENE_SUMMARY_GROUP), backend="api",
    )
    assert [r.status for r in out] == [WeaveStatus.OK] * 3
    names = [{s.type_id: s.value for s in r.strands}[vocab.GENE_NAME] for r in out]
    assert names[1] == "transformation related protein 53"  # mouse summary resolved
    reports = [p for p in calls if p.endswith("/dataset_report")]
    assert len(reports) == 1  # one bulk request for all three genes


async def test_list_orthologs_excludes_query_gene():
    r, _ = await _run(vocab.LIST_ORTHOLOGS, vocab.GENE_ID, "7157", vocab.ORTHOLOG_OUTPUTS)
    sm = {s.type_id: s.value for s in r.strands}
    assert 7157 not in sm[vocab.GENE_ID]  # query gene excluded
    assert set(sm[vocab.GENE_ID]) == {22059, 24842}
    assert sm[vocab.ORTHOLOG_COUNT] == 2


async def test_list_orthologs_taxon_filter():
    r, _ = await _run(vocab.LIST_ORTHOLOGS, vocab.GENE_ID, "7157", vocab.ORTHOLOG_OUTPUTS,
                      params={"taxon_filter": "10090"})
    sm = {s.type_id: s.value for s in r.strands}
    assert sm[vocab.GENE_ID] == [22059]  # mouse only


async def test_orthologs_fan_out_each_drillable():
    from braidworks.core import Braider, BraidRegistry, ExpandPolicy, LocalExecutor

    calls: list[str] = []
    reg = BraidRegistry()
    reg.register(_weaver(calls))
    # gene id -> orthologs (fan on gene.ncbi.id) -> describe_gene each
    braid = Braider(reg).plan(
        available_types=frozenset({vocab.GENE_ID}),
        target_types=frozenset({vocab.ORTHOLOG_COUNT}),
    )
    sets = [StrandSet.from_strands("tp53", [Strand(vocab.GENE_ID, 7157)])]
    result = await LocalExecutor(reg).execute(braid, sets, expand_policy=ExpandPolicy.all())
    assert len(result.resolved) == 2
    assert {ss.get(vocab.GENE_ID).value for ss in result.resolved} == {22059, 24842}
    assert all(ss.parent_id == "tp53" for ss in result.resolved)
