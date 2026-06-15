"""A tiny, deterministic UniProt ID-mapping stand-in for ``weaverkit verify --strict``.

The api backend is *always configured* (the service is keyless), so golden would
otherwise hit the live service — flaky and non-reproducible. This serves the three
ID-mapping endpoints (submit -> poll -> results) for one known mapping: NCBI GeneID
``7157`` (human TP53) -> the canonical accession ``P04637``. The shape mirrors the real
async flow so the engine is exercised exactly as in production.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs

import httpx


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    # Submit: echo the target db into the job id so results can stay deterministic.
    if path.endswith("/idmapping/run"):
        form = parse_qs(request.content.decode())
        to_db = (form.get("to") or [""])[0]
        return httpx.Response(200, content=json.dumps({"jobId": f"job-{to_db}"}))
    if "/idmapping/status/" in path:
        return httpx.Response(200, content=json.dumps({"jobStatus": "FINISHED"}))
    # Results: GeneID 7157 -> P04637 (both the reviewed and the full job), so the golden
    # is a single, deterministic accession (count = 1).
    if "/idmapping/results/" in path:
        return httpx.Response(200, content=json.dumps({"results": [{"from": "7157", "to": "P04637"}]}))
    return httpx.Response(404, content=json.dumps({"detail": "not found"}))


def mock_client() -> httpx.AsyncClient:
    """An ``httpx.AsyncClient`` serving the canned ID-mapping responses (no network)."""
    return httpx.AsyncClient(
        base_url="https://uniprot.test", transport=httpx.MockTransport(_handler)
    )
