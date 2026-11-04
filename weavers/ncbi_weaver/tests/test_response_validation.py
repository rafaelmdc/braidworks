"""NCBI expected source failures are values; sibling successes remain usable."""

import asyncio
import json

import httpx
import pytest
from ncbi_weaver import vocab
from ncbi_weaver.backends import datasets_v2 as api
from ncbi_weaver.backends.datasets_v2 import DatasetsV2Backend
from ncbi_weaver.intermediate import TaxonMatchStatus


@pytest.mark.parametrize(
    "operation",
    ["taxonomy", "children", "genomes", "genome_detail", "gene", "gene_detail", "orthologs"],
)
@pytest.mark.parametrize(
    "body",
    [
        b"broken",
        b"null",
        b"{}",
        b'{"reports":[null]}',
        b'{"reports":[{"taxonomy":[],"gene":[],"accession":null}]}',
    ],
)
async def test_malformed_responses_become_values(operation, body):
    async with httpx.AsyncClient(
        base_url="https://source",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body)),
    ) as client:
        backend = DatasetsV2Backend(client=client)
        if operation == "taxonomy":
            result = await backend.resolve(vocab.DESCRIBE_TAXON, ["9606"], need_lineage=False)
            assert result[0].status is TaxonMatchStatus.ERROR and result[0].error
            return
        calls = {
            "children": lambda: backend.list_children([{vocab.TAXON_ID: "1"}], rank="species"),
            "genomes": lambda: backend.list_genomes([{vocab.TAXON_ID: "1"}]),
            "genome_detail": lambda: backend.describe_genome(
                [{vocab.GENOME_ACCESSION: "GCF_1"}], groups=frozenset()
            ),
            "gene": lambda: backend.resolve_gene([{vocab.PROTEIN_QUERY: "TP53"}], taxon="9606"),
            "gene_detail": lambda: backend.describe_gene(
                [{vocab.GENE_ID: "1"}], groups=frozenset()
            ),
            "orthologs": lambda: backend.list_orthologs([{vocab.GENE_ID: "1"}]),
        }
        records = await calls[operation]()
        assert records[0].error and not records[0].found


async def test_taxonomy_chunk_failure_is_isolated(monkeypatch):
    monkeypatch.setattr(api, "_PAGE_LIMIT", 1)

    def handler(request):
        key = json.loads(request.content)["taxons"][0]
        if key == "Bad":
            return httpx.Response(503)
        return httpx.Response(
            200,
            json={
                "reports": [
                    {"query": [key], "taxonomy": {"tax_id": 9606, "organism_name": "Homo sapiens"}}
                ]
            },
        )

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        results = await DatasetsV2Backend(client=client).resolve(
            vocab.DESCRIBE_TAXON, ["Good", "Bad", "Good", ""], need_lineage=False
        )
    assert [r.status for r in results] == [
        TaxonMatchStatus.RESOLVED,
        TaxonMatchStatus.ERROR,
        TaxonMatchStatus.RESOLVED,
        TaxonMatchStatus.NO_MATCH,
    ]


@pytest.mark.parametrize("status", [400, 404, 503])
async def test_taxonomy_endpoint_status_policy(status):
    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(lambda r: httpx.Response(status))
    ) as client:
        results = await DatasetsV2Backend(client=client).resolve(
            vocab.DESCRIBE_TAXON, ["Bad"], need_lineage=False
        )
    assert results[0].status is (
        TaxonMatchStatus.ERROR if status == 503 else TaxonMatchStatus.NO_MATCH
    )


async def test_suggestion_failure_is_isolated():
    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={"reports": []})
        return (
            httpx.Response(200, json={"sci_name_and_ids": [None]})
            if request.url.path.endswith("Bad")
            else httpx.Response(200, json={"sci_name_and_ids": [{"tax_id": 1, "sci_name": "Good"}]})
        )

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        results = await DatasetsV2Backend(client=client).resolve(
            vocab.RESOLVE_NAME, ["Bad", "Good"], need_lineage=False
        )
    assert (
        results[0].status is TaxonMatchStatus.ERROR
        and results[1].status is TaxonMatchStatus.FUZZY_UNIQUE
    )


@pytest.mark.parametrize("kind", ["gene", "genome"])
async def test_requested_enrichment_failure_is_scoped(kind):
    key = vocab.GENE_ID if kind == "gene" else vocab.GENOME_ACCESSION
    identifiers = ["1", "2"] if kind == "gene" else ["GCF_1", "GCF_2"]

    def handler(request):
        if request.url.path.endswith("dataset_report"):
            rows = (
                [{"gene": {"gene_id": int(identifier)}} for identifier in identifiers]
                if kind == "gene"
                else [{"accession": identifier} for identifier in identifiers]
            )
            return httpx.Response(200, json={"reports": rows})
        return (
            httpx.Response(200, content=b"null")
            if "/" + identifiers[0] + "/" in request.url.path
            else httpx.Response(200, json={"reports": []})
        )

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        backend = DatasetsV2Backend(client=client)
        queries = [{key: identifier} for identifier in identifiers]
        results = (
            await backend.describe_gene(queries, groups=frozenset({"products"}))
            if kind == "gene"
            else await backend.describe_genome(queries, groups=frozenset({"sequences"}))
        )
    assert results[0].error and not results[0].found
    assert results[1].found and not results[1].error


@pytest.mark.parametrize("failure", [asyncio.CancelledError, RuntimeError, ValueError])
async def test_control_and_programming_faults_propagate(failure):
    async def handler(request):
        raise failure()

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(failure):
            await DatasetsV2Backend(client=client).resolve(
                vocab.DESCRIBE_TAXON, ["1"], need_lineage=False
            )


async def test_lineage_chunk_failure_only_affects_dependent_match(monkeypatch):
    monkeypatch.setattr(api, "_PAGE_LIMIT", 1)

    def handler(request):
        key = json.loads(request.content)["taxons"][0]
        if key == "1":
            return httpx.Response(503)
        nodes = {
            "Bad": {"tax_id": 100, "organism_name": "Bad", "parents": [1]},
            "Good": {"tax_id": 200, "organism_name": "Good", "parents": [2]},
            "2": {"tax_id": 2, "organism_name": "Good ancestor"},
        }
        return httpx.Response(200, json={"reports": [{"query": [key], "taxonomy": nodes[key]}]})

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        results = await DatasetsV2Backend(client=client).resolve(
            vocab.DESCRIBE_TAXON, ["Bad", "Good"], need_lineage=True
        )
    assert results[0].status is TaxonMatchStatus.ERROR and "lineage" in results[0].error
    assert results[1].status is TaxonMatchStatus.RESOLVED
    assert results[1].lineage[0].name == "Good ancestor"
