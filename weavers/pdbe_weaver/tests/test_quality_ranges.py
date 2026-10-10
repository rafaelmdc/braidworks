"""Quality is requested separately; mapping spans keep chain/source identities."""

import httpx
from pdbe_weaver.backends.api import PdbeApiBackend, _extract


def test_mapping_spans_retain_distinct_chains_and_display_fan_limits():
    rows = [
        {
            "pdb_id": "1tup",
            "chain_id": chain,
            "coverage": 0.5,
            "unp_start": start,
            "unp_end": end,
            "start": 2,
            "end": 52,
        }
        for chain, start, end in [("A", 1, 50), ("B", 100, 149)]
    ]
    result = _extract(rows, 1)
    chains = result["structure.pdb.records"][0]["chains"]
    assert [c["ranges"]["uniprot"]["start"] for c in chains] == [1, 100]
    assert all(c["source"]["chain_id"] == c["chain_id"] for c in chains)
    assert all(
        "author numbering not inferred" in c["ranges"]["structure"]["namespace"] for c in chains
    )
    assert result["pdb.id"] == ["1tup"] and result["structure.pdb.count"] == 1


async def test_quality_batches_many_into_one_request_and_defaults_skip_it():
    calls = []

    def handler(request):
        calls.append(request)
        ids = request.content.decode().split(",")
        if "summary_quality_scores" in request.url.path:
            return httpx.Response(
                200,
                json={
                    pid: {
                        "geometry_quality": 1.73,
                        "data_quality": None,
                        "experiment_data_available": False,
                    }
                    for pid in ids
                },
            )
        return httpx.Response(
            200,
            json={
                pid: [{"title": "fixture", "experimental_method": ["X-ray diffraction"]}]
                for pid in ids
            },
        )

    async with httpx.AsyncClient(
        base_url="https://fixture", transport=httpx.MockTransport(handler)
    ) as client:
        backend = PdbeApiBackend(client=client)
        queries = [{"pdb.id": "1tup"}, {"pdb.id": "4hhb"}, {"pdb.id": "1tup"}]
        records = await backend.fetch(
            "describe_structure",
            queries,
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"quality"}),
        )
        assert len(calls) == 2 and len(calls[1].content.decode().split(",")) == 2
        assert all(r.found for r in records)
        quality = records[0].values["structure.pdb.quality"]
        assert quality["metrics"]["data_quality"] is None
        assert quality["method"] == ["X-ray diffraction"]
        quality["metrics"]["geometry_quality"] = 99
        assert records[2].values["structure.pdb.quality"]["metrics"]["geometry_quality"] == 1.73
        await backend.fetch(
            "describe_structure",
            queries,
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"detail"}),
        )
        assert len(calls) == 3 and "summary_quality_scores" not in calls[-1].url.path
