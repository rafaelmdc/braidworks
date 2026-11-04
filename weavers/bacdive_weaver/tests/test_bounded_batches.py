"""Distinct taxonomy chains retain the bulk detail endpoint and input correlation."""

import asyncio

import httpx
import pytest
from bacdive_weaver.backends.api import BacdiveApiBackend
from braidworks.core.http_pacing import request_budget


async def fetch(backend, queries):
    return await backend.fetch(
        "describe_traits", queries, requested_outputs=frozenset(), groups_to_compute=frozenset()
    )


async def test_bounded_distinct_scans_keep_bulk_details_and_input_order():
    active = peak = 0
    calls, charges = [], []

    async def handler(request):
        nonlocal active, peak
        calls.append(request.url.path)
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.01)
            species_names = {1: "A a", 3: "B b", 5: "C c"}
            if "/taxon/" in request.url.path:
                name = " ".join(request.url.path.split("/")[-2:])
                first = next(
                    identifier for identifier, species in species_names.items() if species == name
                )
                return httpx.Response(200, json={"results": [first, first + 1], "next": None})
            identifiers = [
                int(identifier) for identifier in request.url.path.rsplit("/", 1)[-1].split(";")
            ]
            return httpx.Response(
                200,
                json={
                    "results": {
                        str(identifier): {
                            "Name and taxonomic classification": {
                                "type strain": "yes" if identifier % 2 == 0 else "no",
                                "species": species_names[
                                    identifier if identifier % 2 else identifier - 1
                                ],
                            }
                        }
                        for identifier in identifiers
                    }
                },
            )
        finally:
            active -= 1

    async def charge(*target):
        charges.append(target)

    queries = [
        {"organism.scientific_name": name, "position": i}
        for i, name in enumerate(["A a", "B b", "A a", "C c"])
    ]
    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        with request_budget(charge):
            records = await fetch(BacdiveApiBackend(client=client, max_concurrency=2), queries)
    assert peak == 2 and active == 0
    assert len(calls) == len(charges) == 6
    assert sum("/fetch/" in path and ";" in path for path in calls) == 3
    assert [r.query for r in records] == queries and all(r.found for r in records)
    assert records[0] is not records[2]


async def test_cancellation_stops_remaining_scans():
    started = asyncio.Event()
    active = 0
    calls = []

    async def handler(request):
        nonlocal active
        calls.append(request)
        active += 1
        if active == 2:
            started.set()
        try:
            await asyncio.Event().wait()
        finally:
            active -= 1

    async def charge(*_):
        pass

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        with request_budget(charge):
            task = asyncio.create_task(
                fetch(
                    BacdiveApiBackend(client=client, max_concurrency=2),
                    [{"organism.scientific_name": f"A {i}"} for i in range(10)],
                )
            )
            await asyncio.wait_for(started.wait(), 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    assert active == 0 and len(calls) == 2


@pytest.mark.parametrize("limit", [True, 0, -1, 1.5])
def test_invalid_concurrency_is_rejected(limit):
    with pytest.raises(ValueError, match="max_concurrency"):
        BacdiveApiBackend(max_concurrency=limit)
