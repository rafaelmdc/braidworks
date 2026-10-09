"""A completed NCBI group means every report page was acquired successfully."""

import httpx
import pytest
from braidworks.core import Strand, StrandSet, WeaveStatus
from braidworks.core.cache import InMemoryStrandCache
from braidworks.core.executor import LocalExecutor
from braidworks.core.planner import Braider
from braidworks.core.registry import BraidRegistry
from braidworks.core.sqlite_cache import SQLiteStrandCache
from ncbi_weaver import vocab
from ncbi_weaver.backends.datasets_v2 import DatasetsV2Backend, _InvalidResponse
from ncbi_weaver.weaver import NCBITaxonWeaver


@pytest.mark.parametrize(
    "collector",
    ["children", "genomes", "genome_reports", "sequences", "gene_reports", "products", "orthologs"],
)
@pytest.mark.parametrize("budget", [1, 1000])
async def test_page_cycles_and_budgets_fail_closed(collector, budget):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"reports": [], "next_page_token": "repeat"})

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        backend = DatasetsV2Backend(client=client, max_report_pages=budget)
        collectors = {
            "children": lambda: backend._fetch_children("1", "species"),
            "genomes": lambda: backend._fetch_genomes("1", {}),
            "genome_reports": lambda: backend._genome_reports(["GCF_1"]),
            "sequences": lambda: backend._fetch_sequences("GCF_1"),
            "gene_reports": lambda: backend._gene_reports(["1"]),
            "products": lambda: backend._fetch_gene_products("1"),
            "orthologs": lambda: backend._fetch_orthologs("1", None),
        }
        with pytest.raises(_InvalidResponse, match="complete=false"):
            await collectors[collector]()
    assert len(calls) == (1 if budget == 1 else 2)


@pytest.mark.parametrize("kind", ["products", "sequences"])
async def test_enrichment_collects_all_pages_without_silent_200_cap(kind):
    calls = []

    def handler(request):
        token = request.url.params.get("page_token")
        calls.append(token)
        indices = range(200) if token is None else [200]
        rows = (
            [{"product": {"transcripts": [{"accession_version": f"NM_{i}"}]}} for i in indices]
            if kind == "products"
            else [{"sequence_name": f"contig{i}"} for i in indices]
        )
        body = {"reports": rows}
        if token is None:
            body["next_page_token"] = "second"
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        backend = DatasetsV2Backend(client=client)
        rows = await (
            backend._fetch_gene_products("1")
            if kind == "products"
            else backend._fetch_sequences("GCF_1")
        )
    assert len(rows) == 201 and calls == [None, "second"]


@pytest.mark.parametrize("kind", ["gene", "genome"])
@pytest.mark.parametrize("persistent", [False, True])
async def test_failed_requested_enrichment_has_no_groups_and_is_never_cached(
    tmp_path, kind, persistent
):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("dataset_report"):
            return httpx.Response(
                200,
                json={
                    "reports": [
                        {"gene": {"gene_id": 1}} if kind == "gene" else {"accession": "GCF_1"}
                    ]
                },
            )
        return httpx.Response(503)

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        weaver = NCBITaxonWeaver({"api": DatasetsV2Backend(client=client)})
        key, value, output, capability = (
            (vocab.GENE_ID, "1", vocab.GENE_PRODUCTS, vocab.DESCRIBE_GENE)
            if kind == "gene"
            else (vocab.GENOME_ACCESSION, "GCF_1", vocab.SEQUENCE_RECORDS, vocab.DESCRIBE_GENOME)
        )
        inputs = lambda: [StrandSet.from_strands("one", [Strand(key, value)])]
        direct = (
            await weaver.execute_batch(
                capability, inputs(), requested_outputs=frozenset({output}), backend="api"
            )
        )[0]
        assert direct.status is WeaveStatus.ERROR and not direct.computed_groups
        registry = BraidRegistry()
        registry.register(weaver)
        cache = SQLiteStrandCache(tmp_path / "cache") if persistent else InMemoryStrandCache()
        executor = LocalExecutor(registry, cache=cache)
        braid = Braider(registry).plan(frozenset({key}), frozenset({output}))
        calls.clear()
        await executor.execute(braid, inputs())
        await executor.execute(braid, inputs())
        assert len(calls) == 4  # each retry performs summary + requested enrichment
