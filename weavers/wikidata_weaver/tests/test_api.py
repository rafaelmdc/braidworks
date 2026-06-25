"""Offline api-backend tests for wikidata_weaver — rank disambiguation of homonyms.

Drives the api backend through the mock client (no network). The homonym case is
"Pholidota": an orchid genus (botany) AND the pangolin order (zoology) both carry
P225 "Pholidota". Without help the name is AMBIGUOUS; the ``expected_rank`` param
collapses it to the single rank-matching item.
"""

from __future__ import annotations

from urllib.parse import unquote_plus

import httpx

from braidworks.core import MatchStatus, Strand, StrandSet, WeaveStatus

from wikidata_weaver import factory
from wikidata_weaver.backends import api
from wikidata_weaver.backends.api import WikidataApiBackend


def _weaver():
    return factory.build_wikidata_weaver_fixture()


async def _resolve(name: str, *, params=None):
    ss = StrandSet.from_strands("e1", [Strand("organism.scientific_name", name)])
    return (
        await _weaver().execute_batch(
            "resolve_taxon",
            [ss],
            requested_outputs=frozenset({"wikipedia.title", "organism.vernacular_names"}),
            backend="api",
            params=params,
        )
    )[0]


async def test_homonym_is_ambiguous_without_rank():
    # Both the orchid genus and the pangolin order match P225 "Pholidota".
    result = await _resolve("Pholidota")
    assert result.status is WeaveStatus.AMBIGUOUS


async def test_expected_rank_disambiguates_to_the_animal():
    # rank=order picks the pangolin order, not the orchid genus.
    result = await _resolve("Pholidota", params={"expected_rank": "order"})
    assert result.status is WeaveStatus.OK
    produced = {s.type_id: s.value for s in result.strands}
    assert produced["wikipedia.title"] == "Pangolin"


async def test_expected_rank_with_no_unique_match_stays_ambiguous():
    # rank=family matches neither candidate (genus/order) -> left ambiguous, not forced.
    result = await _resolve("Pholidota", params={"expected_rank": "family"})
    assert result.status is WeaveStatus.AMBIGUOUS


async def test_single_match_is_unaffected_by_rank():
    # A non-homonym still resolves; the param only acts on multi-item names.
    result = await _resolve("Ursus arctos", params={"expected_rank": "species"})
    assert result.status is WeaveStatus.OK
    produced = {s.type_id: s.value for s in result.strands}
    assert produced["wikipedia.title"] == "Brown_bear"


# --- transient-failure resilience (WDQS flakiness) ------------------------------------

def _good_for(name: str) -> dict:
    """A minimal valid SPARQL-results payload resolving `name` to one English item."""
    return {
        "head": {"vars": ["sname", "item", "article", "vn"]},
        "results": {"bindings": [{
            "sname": {"type": "literal", "value": name},
            "item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q1"},
            "article": {"type": "uri", "value": "https://en.wikipedia.org/wiki/Some_title"},
            "vn": {"xml:lang": "en", "type": "literal", "value": "some name"},
        }]},
    }


def _backend(handler) -> WikidataApiBackend:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://query.wikidata.org"
    )
    return WikidataApiBackend(client=client)


async def _fetch(be, *names):
    return await be.fetch(
        "resolve_taxon",
        [{"organism.scientific_name": n} for n in names],
        requested_outputs=frozenset({"wikipedia.title"}),
        groups_to_compute=frozenset(),
    )


async def test_retries_recover_from_a_bad_json_response(monkeypatch):
    # WDQS returns HTTP 200 with a truncated body twice, then a valid one — the chunk
    # should retry and recover (this is the reptilia "JSONDecodeError" crash).
    monkeypatch.setattr(api.asyncio, "sleep", lambda _t: _noop())
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] <= 2:
            return httpx.Response(200, content=b'{"results": {"bindings": [ {',
                                  headers={"content-type": "application/sparql-results+json"})
        return httpx.Response(200, json=_good_for("Ursus arctos"))

    recs = await _fetch(_backend(handler), "Ursus arctos")
    assert calls["n"] == 3  # 2 bad + 1 good
    assert recs[0].status is MatchStatus.RESOLVED


async def test_persistent_failure_errors_instead_of_crashing(monkeypatch):
    monkeypatch.setattr(api.asyncio, "sleep", lambda _t: _noop())
    recs = await _fetch(_backend(lambda r: httpx.Response(503)), "Ursus arctos")
    assert recs[0].status is MatchStatus.ERROR  # not an unhandled exception


async def test_chunk_failure_is_scoped_to_its_own_names(monkeypatch):
    # One name's chunk fails permanently; another's succeeds. The failure must NOT poison
    # the whole batch (the bug behind many fish silently losing enrichment).
    monkeypatch.setattr(api, "_CHUNK", 1)
    monkeypatch.setattr(api.asyncio, "sleep", lambda _t: _noop())

    def handler(request):
        body = unquote_plus(request.content.decode("utf-8", "ignore"))
        if "Gadus chalcogrammus" in body:
            return httpx.Response(503)
        return httpx.Response(200, json=_good_for("Ursus arctos"))

    recs = await _fetch(_backend(handler), "Ursus arctos", "Gadus chalcogrammus")
    by = {r.query["organism.scientific_name"]: r.status for r in recs}
    assert by["Ursus arctos"] is MatchStatus.RESOLVED
    assert by["Gadus chalcogrammus"] is MatchStatus.ERROR


async def _noop():
    return None
