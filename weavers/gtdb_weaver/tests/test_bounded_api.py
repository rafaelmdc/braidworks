"""Name search bounds upstream work and preserves query positions."""

import asyncio

import httpx
from gtdb_weaver.backends.api import GtdbApiBackend


async def test_distinct_names_use_bounded_workers():
    active = peak = 0
    calls = []

    async def handler(request):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        calls.append(request.url.params["search"])
        try:
            await asyncio.sleep(0.002)
            return httpx.Response(200, json={"rows": []})
        finally:
            active -= 1

    async with httpx.AsyncClient(
        base_url="https://source.example", transport=httpx.MockTransport(handler)
    ) as client:
        backend = GtdbApiBackend(client=client, max_concurrency=2)
        queries = [
            {"organism.scientific_name": name} for name in ["one", "two", "one", "three", "four"]
        ]
        records = await backend.fetch(
            "describe_taxonomy",
            queries,
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
        assert peak <= 2 and len(calls) == 4
        assert [record.query for record in records] == queries
        assert not any(record.error for record in records)
        await backend.aclose()
        assert not client.is_closed
