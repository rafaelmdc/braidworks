"""A tiny, deterministic QuickGO stand-in for ``weaverkit verify --strict`` golden.

The api backend is *always configured* (QuickGO needs no key), so golden would
otherwise hit the live service. This module serves a single canned annotation page
for P04637 with three distinct GO terms (one per aspect) plus a duplicate evidence row
(so the dedup path is exercised), shaped like real QuickGO results
(``goId``/``goName``/``goAspect``, with a ``pageInfo``). ``build_quickgo_weaver_fixture()``
(in factory.py) wires the backend to this transport.
"""

from __future__ import annotations

import json

import httpx

_RESULTS = [
    {
        "geneProductId": "UniProtKB:P04637",
        "goId": "GO:0006915",
        "goName": "apoptotic process",
        "goAspect": "biological_process",
    },
    {
        "geneProductId": "UniProtKB:P04637",
        "goId": "GO:0003700",
        "goName": "DNA-binding transcription factor activity",
        "goAspect": "molecular_function",
    },
    {
        "geneProductId": "UniProtKB:P04637",
        "goId": "GO:0005634",
        "goName": "nucleus",
        "goAspect": "cellular_component",
    },
    # duplicate evidence row for an already-seen term -> must collapse to one term.
    {
        "geneProductId": "UniProtKB:P04637",
        "goId": "GO:0006915",
        "goName": "apoptotic process",
        "goAspect": "biological_process",
    },
]


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/annotation/search"):
        acc = request.url.params.get("geneProductId", "")
        results = _RESULTS if "P04637" in acc else []
        body = {"numberOfHits": len(results), "pageInfo": {"current": 1, "total": 1}, "results": results}
        return httpx.Response(200, content=json.dumps(body))
    return httpx.Response(404, content=json.dumps({"detail": "not found"}))


def mock_client() -> httpx.AsyncClient:
    """An ``httpx.AsyncClient`` serving the canned QuickGO responses (no network)."""
    return httpx.AsyncClient(
        base_url="https://quickgo.test/services", transport=httpx.MockTransport(_handler)
    )
