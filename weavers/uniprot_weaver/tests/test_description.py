"""Exact accession, evidence preservation, group costs and bulk failure boundaries."""

import asyncio
import json
import re
from copy import deepcopy

import httpx
import pytest
from braidworks.core import Strand, StrandSet, WeaveStatus
from uniprot_weaver.backends.api import UniprotApiBackend
from uniprot_weaver.backends.description import ANNOTATIONS, SEQUENCE
from uniprot_weaver.factory import build_uniprot_weaver_fixture

ACC = "protein.uniprot.accession"
ENTRY = {
    "primaryAccession": "P04637",
    "entryType": "UniProtKB reviewed (Swiss-Prot)",
    "organism": {"taxonId": 9606, "scientificName": "Homo sapiens"},
    "sequence": {"value": "MTEST", "length": 5},
    "comments": [
        {
            "commentType": "FUNCTION",
            "texts": [
                {
                    "value": "Test function (PubMed:1)",
                    "evidences": [{"evidenceCode": "ECO:0000269", "source": "PubMed", "id": "1"}],
                }
            ],
        }
    ],
    "features": [
        {
            "type": "Active site",
            "location": {
                "start": {"value": 2, "modifier": "EXACT"},
                "end": {"value": 2, "modifier": "EXACT"},
            },
            "evidences": [{"evidenceCode": "ECO:0000269", "source": "PubMed", "id": "1"}],
        }
    ],
    "references": [{"citation": {"id": "1"}}],
    "entryAudit": {"entryVersion": 1},
}


async def lookup(handler, queries, outputs=frozenset({ACC})):
    async with httpx.AsyncClient(
        base_url="https://u", transport=httpx.MockTransport(handler)
    ) as client:
        return await UniprotApiBackend(client=client).fetch(
            "describe_protein", queries, requested_outputs=outputs, groups_to_compute=frozenset()
        )


@pytest.mark.parametrize(
    "outputs",
    [
        frozenset({ACC}),
        frozenset({SEQUENCE}),
        frozenset({ANNOTATIONS}),
        frozenset({SEQUENCE, ANNOTATIONS}),
    ],
)
async def test_groups_control_projection_and_preserve_raw_evidence(outputs):
    calls = []
    before = deepcopy(ENTRY)

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200, json={"results": [ENTRY]}, headers={"x-uniprot-release": "fixture"}
        )

    record = (await lookup(handler, [{ACC: "P04637"}], outputs))[0]
    assert record.found and not record.error and ENTRY == before
    assert (SEQUENCE in record.values) == (SEQUENCE in outputs)
    assert (ANNOTATIONS in record.values) == (ANNOTATIONS in outputs)
    fields = calls[0].url.params.get("fields", "")
    assert (not fields) == (ANNOTATIONS in outputs)
    if ANNOTATIONS not in outputs:
        assert ("sequence" in fields.split(",")) == (SEQUENCE in outputs)
    if ANNOTATIONS in outputs:
        evidence = record.values[ANNOTATIONS]
        assert evidence["comments"] == ENTRY["comments"]
        assert evidence["features"] == ENTRY["features"]
        assert evidence["references"] == ENTRY["references"]
        assert evidence["entryAudit"] == ENTRY["entryAudit"]
        assert evidence["release"] == {"version": "fixture"}


async def test_describe_batches_many_into_one_request_and_detaches_duplicates():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        **ENTRY,
                        "primaryAccession": "A0A087WT22",
                        "entryType": "UniProtKB unreviewed (TrEMBL)",
                    },
                    ENTRY,
                ]
            },
        )

    queries = [{ACC: acc} for acc in ["p04637", "A0A087WT22", "P04637", "Q99999", "P04637-2", ""]]
    records = await lookup(handler, queries, frozenset({ANNOTATIONS}))
    assert len(calls) == 1 and [record.query for record in records] == queries
    assert [record.found for record in records] == [True, True, True, False, False, False]
    assert "reviewed:true" not in calls[0].url.params["query"]
    assert records[1].values["protein.reviewed"] == "unreviewed"
    records[0].values[ANNOTATIONS]["features"][0]["type"] = "changed"
    assert records[2].values[ANNOTATIONS]["features"][0]["type"] == "Active site"


async def test_chunk_failure_preserves_other_chunk_and_original_order():
    calls = []

    def handler(request):
        ids = re.findall(r"accession:([A-Z0-9]+)", request.url.params["query"])
        calls.append(ids)
        if len(ids) == 25:
            return httpx.Response(503)
        return httpx.Response(200, json={"results": [{**ENTRY, "primaryAccession": ids[0]}]})

    ids = [f"P{i:05d}" for i in range(26)]
    queries = [{ACC: acc} for acc in reversed(ids)]
    records = await lookup(handler, queries)
    assert len(calls) == 2 and calls[0] == ids[:25] and calls[1] == ids[25:]
    assert records[0].found and not records[0].error
    assert all(record.error and not record.found for record in records[1:])
    assert [record.query for record in records] == queries


@pytest.mark.parametrize(
    "entry",
    [
        {**ENTRY, "sequence": None},
        {**ENTRY, "sequence": {"value": "MTEST", "length": 4}},
        {**ENTRY, "sequence": {"value": "not sequence", "length": 12}},
    ],
)
async def test_bad_requested_sequence_is_entry_error_with_good_sibling(entry):
    records = await lookup(
        lambda request: httpx.Response(
            200, json={"results": [entry, {**ENTRY, "primaryAccession": "Q00987"}]}
        ),
        [{ACC: "P04637"}, {ACC: "Q00987"}],
        frozenset({SEQUENCE}),
    )
    assert records[0].error and records[1].found and not records[1].error


@pytest.mark.parametrize(
    "patch",
    [
        {"features": None},
        {"features": [None]},
        {"references": [{"citation": []}]},
        {"features": [{"type": "Site", "evidences": "bad"}]},
        {"features": [{"type": "Site", "evidences": [{"evidenceCode": None}]}]},
        {"features": [{"type": "Site", "score": float("nan")}]},
    ],
)
async def test_invalid_annotations_are_errors(patch):
    record = (
        await lookup(
            lambda r: httpx.Response(200, content=json.dumps({"results": [{**ENTRY, **patch}]})),
            [{ACC: "P04637"}],
            frozenset({ANNOTATIONS}),
        )
    )[0]
    assert record.error and not record.found


async def test_valid_sparse_annotations_are_empty_not_invented():
    record = (
        await lookup(
            lambda r: httpx.Response(200, json={"results": [{"primaryAccession": "P04637"}]}),
            [{ACC: "P04637"}],
            frozenset({ANNOTATIONS}),
        )
    )[0]
    assert record.found and record.values[ANNOTATIONS] == {
        "comments": [],
        "features": [],
        "references": [],
        "release": {},
    }


async def test_secondary_search_hit_cannot_replace_exact_primary_identity():
    record = (
        await lookup(lambda r: httpx.Response(200, json={"results": [ENTRY]}), [{ACC: "Q99999"}])
    )[0]
    assert not record.found and not record.error


@pytest.mark.parametrize("status", [400, 404, 500])
async def test_description_status_convention(status):
    record = (await lookup(lambda r: httpx.Response(status), [{ACC: "P04637"}]))[0]
    assert not record.found and bool(record.error) == (status == 500)


@pytest.mark.parametrize("failure", [asyncio.CancelledError, RuntimeError])
async def test_control_and_programming_faults_propagate(failure):
    async def handler(request):
        raise failure()

    with pytest.raises(failure):
        await lookup(handler, [{ACC: "P04637"}])


async def test_fixture_sequence_and_annotations_execute_with_declared_groups():
    async with build_uniprot_weaver_fixture() as weaver:
        result = await weaver.execute(
            "describe_protein",
            StrandSet.from_strands("p53", [Strand(ACC, "P04637")]),
            requested_outputs=frozenset({SEQUENCE, ANNOTATIONS, "protein.length"}),
            backend="api",
        )
    assert result.status is WeaveStatus.OK
    assert result.computed_groups == frozenset({"identity", "sequence", "annotations"})
    values = {strand.type_id: strand.value for strand in result.strands}
    assert len(values[SEQUENCE]) == values["protein.length"] == 393
    assert values[ANNOTATIONS]["features"]


@pytest.mark.parametrize(
    "mode",
    [
        "second_page_failure",
        "repeat",
        "budget",
        "malformed",
        "invalid_json",
        "duplicate",
        "bad_envelope",
        "empty_link",
        "invalid_link",
    ],
)
async def test_pagination_or_envelope_failure_never_returns_partial_success(mode):
    pages = []

    def handler(request):
        pages.append(request.url.path)
        if mode == "invalid_json":
            return httpx.Response(200, content=b"invalid")
        if mode == "bad_envelope":
            return httpx.Response(200, json={})
        if mode == "duplicate":
            return httpx.Response(200, json={"results": [ENTRY, ENTRY]})
        if len(pages) > 1 and mode == "second_page_failure":
            return httpx.Response(404)
        if mode == "empty_link":
            return httpx.Response(
                200, json={"results": [ENTRY]}, headers={"Link": '<>; rel="next"'}
            )
        if mode == "invalid_link":
            return httpx.Response(
                200, json={"results": [ENTRY]}, headers={"Link": '<ftp://u/page2>; rel="next"'}
            )
        link = (
            'garbage; rel="next"'
            if mode == "malformed"
            else (
                f'<https://u/page{len(pages)}>; rel="next"'
                if mode == "budget"
                else '<https://u/page2>; rel="next"'
            )
        )
        rows = [ENTRY] if len(pages) == 1 else []
        return httpx.Response(200, json={"results": rows}, headers={"Link": link})

    record = (await lookup(handler, [{ACC: "P04637"}]))[0]
    assert record.error and not record.found and record.values == {}
    assert len(pages) <= 10


async def test_two_pages_remap_by_identity_not_response_position():
    def handler(request):
        if request.url.path == "/uniprotkb/search":
            return httpx.Response(
                200,
                json={"results": [{**ENTRY, "primaryAccession": "Q00987"}]},
                headers={"Link": '<https://u/page2>; rel="next"'},
            )
        assert not request.url.params
        return httpx.Response(200, json={"results": [ENTRY]})

    records = await lookup(handler, [{ACC: "P04637"}, {ACC: "Q00987"}])
    assert [record.values[ACC] for record in records] == ["P04637", "Q00987"]


@pytest.mark.parametrize("persistent", [False, True])
@pytest.mark.parametrize(
    "outputs",
    [
        (SEQUENCE, "protein.length"),
        ("protein.length", SEQUENCE),
        (SEQUENCE, ANNOTATIONS),
        (ANNOTATIONS, SEQUENCE),
    ],
)
async def test_description_groups_do_not_satisfy_other_group_cache(tmp_path, persistent, outputs):
    from braidworks.core.cache import InMemoryStrandCache
    from braidworks.core.executor import LocalExecutor
    from braidworks.core.planner import Braider
    from braidworks.core.registry import BraidRegistry
    from braidworks.core.sqlite_cache import SQLiteStrandCache
    from uniprot_weaver.weaver import UniprotWeaver

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"results": [ENTRY]})

    async with httpx.AsyncClient(
        base_url="https://u", transport=httpx.MockTransport(handler)
    ) as client:
        registry = BraidRegistry()
        registry.register(UniprotWeaver({"api": UniprotApiBackend(client=client)}))
        cache = SQLiteStrandCache(tmp_path / "cache") if persistent else InMemoryStrandCache()
        executor = LocalExecutor(registry, cache=cache)
        for output in outputs:
            braid = Braider(registry).plan(frozenset({ACC}), frozenset({output}))
            result = await executor.execute(
                braid, [StrandSet.from_strands("p53", [Strand(ACC, "P04637")])]
            )
            assert result.resolved and result.resolved[0].get(output) is not None
        assert len(calls) == 2
