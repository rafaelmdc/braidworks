"""A tiny, deterministic STRING stand-in for ``weaverkit verify --strict`` golden.

The api backend is *always configured* (STRING REST needs no key), so golden would
otherwise hit the live service. This module serves a canned ``interaction_partners``
response for P04637 (human TP53) with two partners, shaped like real STRING edges
(``preferredName_B``, combined ``score``, per-channel subscores) so the mapping path
runs exactly as in production. ``build_string_weaver_fixture()`` (in factory.py) wires
the backend to this transport.
"""

from __future__ import annotations

import json

import httpx

# Two partners of TP53 (real STRING shape); deliberately given out of score order so
# the deterministic sort (score desc, then name) is exercised by the golden run.
_P04637_PARTNERS = [
    {
        "stringId_A": "9606.ENSP00000269305",
        "stringId_B": "9606.ENSP00000478207",
        "preferredName_A": "TP53",
        "preferredName_B": "MDM2",
        "ncbiTaxonId": 9606,
        "score": 0.999,
        "escore": 0.962,
        "dscore": 0.9,
        "tscore": 0.913,
    },
    {
        "stringId_A": "9606.ENSP00000269305",
        "stringId_B": "9606.ENSP00000340989",
        "preferredName_A": "TP53",
        "preferredName_B": "SFN",
        "ncbiTaxonId": 9606,
        "score": 0.95,
        "escore": 0.5,
        "tscore": 0.7,
    },
]


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/interaction_partners"):
        ids = request.url.params.get("identifiers", "")
        partners = _P04637_PARTNERS if "P04637" in ids else []
        return httpx.Response(200, content=json.dumps(partners))
    return httpx.Response(404, content=json.dumps({"detail": "not found"}))


def mock_client() -> httpx.AsyncClient:
    """An ``httpx.AsyncClient`` serving the canned STRING responses (no network)."""
    return httpx.AsyncClient(
        base_url="https://string.test/api", transport=httpx.MockTransport(_handler)
    )
