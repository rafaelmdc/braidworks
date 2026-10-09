"""SPARQL schema, query literals, retry budgets and chunk isolation."""

import asyncio
import json

import httpx
import pytest
from braidworks.core import MatchStatus
from wikidata_weaver.backends import api
from wikidata_weaver.backends.api import WikidataApiBackend, _sparql_literal


def good(name="Good species"):
    return {
        "results": {
            "bindings": [
                {"sname": {"value": name}, "item": {"value": "http://www.wikidata.org/entity/Q1"}}
            ]
        }
    }


async def fetch(handler, names=("Bad species", "Good species")):
    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        return await WikidataApiBackend(client=client).fetch(
            "resolve_taxon",
            [{"organism.scientific_name": name} for name in names],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )


@pytest.mark.parametrize(
    "body",
    [
        b"broken",
        b"null",
        b"{}",
        b"[]",
        b'{"results":{"bindings":[null]}}',
        b'{"results":{"bindings":[{"sname":null,"item":{}}]}}',
    ],
)
async def test_invalid_payload_is_scoped_to_chunk(monkeypatch, body):
    monkeypatch.setattr(api, "_CHUNK", 1)
    monkeypatch.setattr(api, "_BACKOFF_BASE", 0)

    def handler(request):
        if "Good" in request.content.decode():
            return httpx.Response(200, json=good())
        return httpx.Response(200, content=body)

    records = await fetch(handler)
    assert [r.status for r in records] == [MatchStatus.ERROR, MatchStatus.RESOLVED]
    assert "malformed response" in records[0].error


@pytest.mark.parametrize("status", [400, 404, 401])
async def test_query_service_errors_are_not_absence_or_retried(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status)

    records = await fetch(handler, names=("Taxon",))
    assert len(calls) == 1 and records[0].status is MatchStatus.ERROR
    assert str(status) in records[0].error


@pytest.mark.parametrize("value", ['a"b', "a\\b", "a\nb", "a\rb", "a\tb", "a\x00b", "a\x01b"])
def test_short_literals_escape_controls(value):
    literal = _sparql_literal(value)
    assert json.loads(literal) == value
    assert all(ord(char) >= 32 for char in literal)


async def test_retry_after_honored_within_budget(monkeypatch):
    waits, calls = [], []

    async def sleep(delay):
        waits.append(delay)

    monkeypatch.setattr(api.asyncio, "sleep", sleep)

    def handler(request):
        calls.append(request)
        return (
            httpx.Response(429, headers={"Retry-After": "3"})
            if len(calls) == 1
            else httpx.Response(200, json=good())
        )

    records = await fetch(handler, names=("Good species",))
    assert waits == [3] and records[0].status is MatchStatus.RESOLVED


async def test_long_server_wait_returns_budget_error_without_early_retry(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503, headers={"Retry-After": "3600"})

    records = await fetch(handler, names=("Taxon",))
    assert len(calls) == 1 and records[0].status is MatchStatus.ERROR
    assert "budget" in records[0].error and "503" in records[0].error


async def test_unrequested_echo_is_error():
    records = await fetch(
        lambda r: httpx.Response(200, json=good("Other species")), names=("Taxon",)
    )
    assert records[0].status is MatchStatus.ERROR and "unrequested" in records[0].error


@pytest.mark.parametrize("failure", [asyncio.CancelledError, RuntimeError, ValueError])
async def test_control_and_programming_faults_propagate(failure):
    async def handler(request):
        raise failure()

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(failure):
            await WikidataApiBackend(client=client).fetch(
                "resolve_taxon",
                [{"organism.scientific_name": "Taxon"}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset(),
            )


async def test_elapsed_budget_bounds_slow_request(monkeypatch):
    monkeypatch.setattr(api, "_RETRY_BUDGET", 0.01)

    async def handler(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json=good())

    records = await fetch(handler, names=("Good species",))
    assert records[0].status is MatchStatus.ERROR
    assert "budget exhausted during request" in records[0].error
