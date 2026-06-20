"""A tiny, deterministic stand-in for the api backend — for offline tests.

A keyless API backend is *always configured*, so golden/order tests would hit the
live Wikidata service. This serves canned SPARQL-results JSON via
``httpx.MockTransport`` so ``build_wikidata_weaver_fixture()`` runs offline and
reproducibly. The canned payload is a real response shape for ``Ursus arctos``.
"""

from __future__ import annotations

import json

import httpx

# Real Wikidata SPARQL bindings for `?item wdt:P225 "Ursus arctos"` (one item,
# enwiki sitelink, two English vernacular names). ?sname is echoed back.
_URSUS_ARCTOS = {
    "head": {"vars": ["sname", "item", "article", "vn"]},
    "results": {
        "bindings": [
            {
                "sname": {"type": "literal", "value": "Ursus arctos"},
                "item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q36341"},
                "article": {"type": "uri", "value": "https://en.wikipedia.org/wiki/Brown_bear"},
                "vn": {"xml:lang": "en", "type": "literal", "value": "Brown Bear"},
            },
            {
                "sname": {"type": "literal", "value": "Ursus arctos"},
                "item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q36341"},
                "article": {"type": "uri", "value": "https://en.wikipedia.org/wiki/Brown_bear"},
                "vn": {"xml:lang": "en", "type": "literal", "value": "grizzly bear"},
            },
        ]
    },
}

_EMPTY = {"head": {"vars": ["sname", "item", "article", "vn"]}, "results": {"bindings": []}}


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/sparql"):
        query = request.url.params.get("query", "")
        payload = _URSUS_ARCTOS if "Ursus arctos" in query else _EMPTY
        return httpx.Response(
            200,
            content=json.dumps(payload),
            headers={"Content-Type": "application/sparql-results+json"},
        )
    return httpx.Response(404, content=json.dumps({"detail": "not found"}))


def mock_client() -> httpx.AsyncClient:
    """An ``httpx.AsyncClient`` serving the canned responses (no network)."""
    return httpx.AsyncClient(
        base_url="https://wikidata.test", transport=httpx.MockTransport(_handler)
    )
