"""BacDive taxon absence differs from failure to fetch known strain records."""

import asyncio

import httpx
import pytest
from bacdive_weaver.backends.api import BacdiveApiBackend


async def fetch(handler):
    queries = [
        {"organism.scientific_name": "Bad species"},
        {"organism.scientific_name": "Good species"},
    ]

    def wrapped(request):
        if "/taxon/Good/" in request.url.path:
            return httpx.Response(200, json={"results": [1], "next": None})
        if request.url.path.endswith("/fetch/1"):
            return httpx.Response(
                200,
                json={
                    "results": {"1": {"Name and taxonomic classification": {"type strain": "yes"}}}
                },
            )
        return handler(request)

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(wrapped)
    ) as client:
        return await BacdiveApiBackend(client=client).fetch(
            "describe_traits", queries, requested_outputs=frozenset(), groups_to_compute=frozenset()
        )


@pytest.mark.parametrize(
    "body",
    [
        b"broken",
        b"null",
        b"{}",
        b'{"results":[null]}',
        b'{"results":[true]}',
        b'{"results":[1.5]}',
        b'{"results":["x"]}',
        b'{"results":[],"next":[]}',
    ],
)
async def test_bad_taxon_data_is_isolated(body):
    records = await fetch(lambda r: httpx.Response(200, content=body))
    assert records[0].error and not records[0].found
    assert records[1].found and not records[1].error


@pytest.mark.parametrize("status", [400, 404])
async def test_taxon_absence_is_clean_miss(status):
    records = await fetch(lambda r: httpx.Response(status))
    assert not records[0].found and not records[0].error
    assert records[1].found


@pytest.mark.parametrize(
    "body",
    [
        b"broken",
        b"null",
        b"{}",
        b'{"results":[]}',
        b'{"results":{"2":null}}',
        b'{"results":{"99":{}}}',
        b'{"results":{"2":{"Name and taxonomic classification":[] ,"Morphology":"bad"}}}',
    ],
)
async def test_bad_strain_data_is_error(body):
    def handler(request):
        if "/taxon/" in request.url.path:
            return httpx.Response(200, json={"results": [2], "next": None})
        return httpx.Response(200, content=body)

    records = await fetch(handler)
    assert records[0].error and records[1].found


async def test_known_strain_fetch_404_is_error():
    def handler(request):
        return (
            httpx.Response(200, json={"results": [2], "next": None})
            if "/taxon/" in request.url.path
            else httpx.Response(404)
        )

    records = await fetch(handler)
    assert records[0].error and records[1].found


async def test_cancellation_propagates():
    async def handler(request):
        raise asyncio.CancelledError()

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(asyncio.CancelledError):
            await BacdiveApiBackend(client=client).fetch(
                "describe_traits",
                [{"organism.scientific_name": "Bad species"}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset(),
            )
