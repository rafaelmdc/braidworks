"""A tiny, deterministic Reactome stand-in for ``weaverkit verify --strict`` golden.

The api backend is *always configured* (Reactome needs no key), so golden would
otherwise hit the live service. This module serves a canned ``mapping/.../pathways``
response for P04637 with two distinct pathways **and a duplicate stId** (so the dedup
path is exercised), shaped like real Reactome rows (``stId``/``displayName``/
``isInDisease``). ``build_reactome_weaver_fixture()`` (in factory.py) wires the backend
to this transport.
"""

from __future__ import annotations

import json

import httpx

_PATHWAYS = [
    {"stId": "R-HSA-111448", "displayName": "Activation of NOXA and translocation to mitochondria",
     "schemaClass": "Pathway", "isInDisease": False},
    {"stId": "R-HSA-69541", "displayName": "Stabilization of p53",
     "schemaClass": "Pathway", "isInDisease": False},
    # duplicate stId -> must collapse to one pathway
    {"stId": "R-HSA-111448", "displayName": "Activation of NOXA and translocation to mitochondria",
     "schemaClass": "Pathway", "isInDisease": False},
]


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/pathways") and "/UniProt/" in request.url.path:
        acc = request.url.path.split("/UniProt/")[1].split("/")[0]
        if acc == "P04637":
            return httpx.Response(200, content=json.dumps(_PATHWAYS))
        return httpx.Response(404, content=json.dumps({"messages": ["no pathways"]}))
    return httpx.Response(404, content=json.dumps({"detail": "not found"}))


def mock_client() -> httpx.AsyncClient:
    """An ``httpx.AsyncClient`` serving the canned Reactome responses (no network)."""
    return httpx.AsyncClient(
        base_url="https://reactome.test/ContentService", transport=httpx.MockTransport(_handler)
    )
