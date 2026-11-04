"""Adverse asynchronous mapping lifecycle tests, independent of protein selection."""

import asyncio
from copy import deepcopy
from urllib.parse import parse_qs

import httpx
import pytest
from braidworks.core.http_pacing import PacedHTTPClient
from uniprot_weaver import mapping
from uniprot_weaver.backends.api import UniprotApiBackend
from uniprot_weaver.backends.jobs import MappingJobClient, normalize_mapping_page
from uniprot_weaver.backends.validation import _InvalidResponse


def test_page_normalization_is_pure_distinct_and_correlated():
    body = {
        "results": [
            {"from": "1", "to": "Q2"},
            {"from": "1", "to": {"primaryAccession": "P1"}},
            {"from": "1", "to": "Q2"},
        ],
        "failedIds": ["2"],
    }
    before = deepcopy(body)
    assert normalize_mapping_page(body, frozenset({"1", "2"})) == {"1": ["P1", "Q2"]}
    assert body == before


@pytest.mark.parametrize("failed", [["other"], [1], "1", None])
def test_uncorrelated_failed_ids_are_rejected(failed):
    with pytest.raises(_InvalidResponse):
        normalize_mapping_page({"failedIds": failed}, frozenset({"1"}))


@pytest.mark.parametrize("status", ["RUNNING", "QUEUED", "NEW", "FAILED"])
async def test_poll_budget_or_failed_job_never_fetches_results(status):
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(
            200, json={"jobId": "job"} if request.method == "POST" else {"jobStatus": status}
        )

    async with httpx.AsyncClient(
        base_url="https://u", transport=httpx.MockTransport(handler)
    ) as client:
        jobs = MappingJobClient(PacedHTTPClient(client, "uniprot"), poll_tries=2, poll_delay=0)
        with pytest.raises(httpx.HTTPError, match="failed|did not finish"):
            await jobs.run("GeneID", "UniProtKB", ["1"])
    assert paths.count("/idmapping/status/job") == (1 if status == "FAILED" else 2)
    assert not any("/results/" in path for path in paths)


@pytest.mark.parametrize("mode", ["repeat", "budget", "malformed", "bad_json", "timeout"])
async def test_result_failures_do_not_return_partial_mappings(mode):
    pages = []

    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={"jobId": "job"})
        if "/status/" in request.url.path:
            return httpx.Response(200, json={"jobStatus": "FINISHED"})
        pages.append(request.url.path)
        if mode == "timeout":
            raise httpx.ReadTimeout("result timed out", request=request)
        if mode == "bad_json":
            return httpx.Response(200, content=b"invalid")
        link = 'garbage; rel="next"' if mode == "malformed" else '<https://u/page2>; rel="next"'
        return httpx.Response(
            200, headers={"Link": link}, json={"results": [{"from": "1", "to": "P1"}]}
        )

    async with httpx.AsyncClient(
        base_url="https://u", transport=httpx.MockTransport(handler)
    ) as client:
        jobs = MappingJobClient(
            PacedHTTPClient(client, "uniprot"), max_pages=1 if mode == "budget" else 5
        )
        with pytest.raises((ValueError, httpx.HTTPError)):
            await jobs.run("GeneID", "UniProtKB", ["1"])
    assert len(pages) == (2 if mode == "repeat" else 1)


async def test_success_after_running_status_and_multiple_distinct_inputs():
    statuses = 0
    submitted = []

    def handler(request):
        nonlocal statuses
        if request.method == "POST":
            submitted.extend(parse_qs(request.content.decode())["ids"][0].split(","))
            return httpx.Response(200, json={"jobId": "job"})
        if "/status/" in request.url.path:
            statuses += 1
            return httpx.Response(
                200, json={"jobStatus": "RUNNING" if statuses == 1 else "FINISHED"}
            )
        return httpx.Response(
            200, json={"results": [{"from": "2", "to": "P2"}, {"from": "1", "to": "P1"}]}
        )

    async with httpx.AsyncClient(
        base_url="https://u", transport=httpx.MockTransport(handler)
    ) as client:
        jobs = MappingJobClient(PacedHTTPClient(client, "uniprot"), poll_delay=0)
        assert await jobs.run("GeneID", "UniProtKB", ["1", "2"]) == {"2": ["P2"], "1": ["P1"]}
    assert submitted == ["1", "2"] and statuses == 2


@pytest.mark.parametrize("failure", [httpx.ReadTimeout, RuntimeError, asyncio.CancelledError])
async def test_failed_reviewed_pair_drains_sibling_before_returning(monkeypatch, failure):
    started = asyncio.Event()
    drained = asyncio.Event()
    backend = UniprotApiBackend()

    async def job(from_db, to_db, ids):
        if to_db == mapping.UNIPROT_TO_REVIEWED:
            await started.wait()
            raise failure("stop")
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            drained.set()

    monkeypatch.setattr(backend, "_idmap", job)
    call = backend.fetch(
        mapping.TO_ACCESSION,
        [{"gene.ncbi.id": "1"}],
        requested_outputs=frozenset({mapping.ACCESSION}),
        groups_to_compute=frozenset(),
    )
    if failure is httpx.ReadTimeout:
        assert (await call)[0].error
    else:
        with pytest.raises(failure):
            await call
    assert drained.is_set()


async def test_many_distinct_and_duplicate_inputs_share_two_bulk_requests():
    from tests.test_api import _idmap_backend

    calls = []
    backend = _idmap_backend(
        {
            ("GeneID", mapping.UNIPROT_TO_REVIEWED): {"1": ["P1"], "2": ["P2"], "3": ["P3"]},
            ("GeneID", mapping.UNIPROT_TO): {"1": ["P1"], "2": ["P2"], "3": ["P3"]},
        },
        run_calls=calls,
    )
    queries = [{"gene.ncbi.id": value} for value in ["2", "1", "2", "3"]]
    try:
        records = await backend.fetch(
            mapping.TO_ACCESSION,
            queries,
            requested_outputs=frozenset({mapping.ACCESSION}),
            groups_to_compute=frozenset(),
        )
        assert [record.query for record in records] == queries
        assert [record.values[mapping.ACCESSION] for record in records] == [
            ["P2"],
            ["P1"],
            ["P2"],
            ["P3"],
        ]
        assert calls == [("GeneID", mapping.UNIPROT_TO_REVIEWED), ("GeneID", mapping.UNIPROT_TO)]
    finally:
        await backend._client.aclose()


async def test_failed_target_job_does_not_poison_later_target_request():
    calls = []

    def handler(request):
        if request.method == "POST":
            target = parse_qs(request.content.decode())["to"][0]
            calls.append(target)
            return (
                httpx.Response(503)
                if target == "GeneID"
                else httpx.Response(200, json={"jobId": "good"})
            )
        if "/status/" in request.url.path:
            return httpx.Response(200, json={"jobStatus": "FINISHED"})
        return httpx.Response(200, json={"results": [{"from": "P04637", "to": "1TUP"}]})

    async with httpx.AsyncClient(
        base_url="https://u", transport=httpx.MockTransport(handler)
    ) as client:
        backend = UniprotApiBackend(client=client)

        async def lookup(output):
            return (
                await backend.fetch(
                    mapping.FROM_ACCESSION,
                    [{mapping.ACCESSION: "P04637"}],
                    requested_outputs=frozenset({output}),
                    groups_to_compute=frozenset(),
                )
            )[0]

        assert (await lookup("gene.ncbi.id")).error
        good = await lookup("pdb.id")
        assert good.found and not good.error and good.values["pdb.id"] == ["1TUP"]
    assert calls == ["GeneID", "PDB"]
