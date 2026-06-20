"""A tiny, deterministic stand-in for the api backend — for offline tests.

A keyless API backend is *always configured*, so golden/order tests would hit the
live Wikimedia service. This serves canned pageviews JSON via ``httpx.MockTransport``
so ``build_wikipedia_weaver_fixture()`` runs offline and reproducibly. The canned
"Brown_bear" payload sums to 178774, matching the spec's golden expectation.
"""

from __future__ import annotations

import json

import httpx

# Real Wikimedia pageviews rows for "Brown_bear" (two months: 94587 + 84187 = 178774).
_BROWN_BEAR = {
    "items": [
        {"project": "en.wikipedia", "article": "Brown_bear", "granularity": "monthly",
         "timestamp": "2025010100", "access": "all-access", "agent": "all-agents",
         "views": 94587},
        {"project": "en.wikipedia", "article": "Brown_bear", "granularity": "monthly",
         "timestamp": "2025020100", "access": "all-access", "agent": "all-agents",
         "views": 84187},
    ]
}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if "/per-article/" in path and "/Brown_bear/" in path:
        return httpx.Response(200, content=json.dumps(_BROWN_BEAR))
    if "/per-article/" in path:
        # Any other title: the API returns 404 when it has no data for the article.
        return httpx.Response(404, content=json.dumps({"type": "not_found"}))
    return httpx.Response(404, content=json.dumps({"detail": "not found"}))


def mock_client() -> httpx.AsyncClient:
    """An ``httpx.AsyncClient`` serving the canned responses (no network)."""
    return httpx.AsyncClient(
        base_url="https://wikipedia.test", transport=httpx.MockTransport(_handler)
    )
