"""A tiny, deterministic PDBe stand-in for ``weaverkit verify --strict`` golden.

The api backend is *always configured* (PDBe needs no key), so golden would otherwise
hit the live service. This module serves a canned ``best_structures`` response for
P04637 with **two distinct structures and a duplicate chain of one** (so the dedup +
best-chain path is exercised), shaped like real PDBe rows
(``pdb_id``/``experimental_method``/``resolution``/``coverage``).
``build_pdbe_weaver_fixture()`` (in factory.py) wires the backend to this transport.
"""

from __future__ import annotations

import json

import httpx

_BEST_STRUCTURES = {
    "P04637": [
        {"pdb_id": "1tup", "chain_id": "A", "experimental_method": "X-ray diffraction",
         "resolution": 2.2, "coverage": 0.55},
        # a second chain of the same structure -> must collapse to one, keeping best coverage
        {"pdb_id": "1tup", "chain_id": "B", "experimental_method": "X-ray diffraction",
         "resolution": 2.2, "coverage": 0.52},
        {"pdb_id": "2ahi", "chain_id": "A", "experimental_method": "Electron Microscopy",
         "resolution": 3.5, "coverage": 0.9},
    ]
}


def _handler(request: httpx.Request) -> httpx.Response:
    if "/best_structures/" in request.url.path:
        acc = request.url.path.rsplit("/", 1)[1]
        if acc in _BEST_STRUCTURES:
            return httpx.Response(200, content=json.dumps({acc: _BEST_STRUCTURES[acc]}))
        return httpx.Response(404, content=json.dumps({"detail": "no structures"}))
    return httpx.Response(404, content=json.dumps({"detail": "not found"}))


def mock_client() -> httpx.AsyncClient:
    """An ``httpx.AsyncClient`` serving the canned PDBe responses (no network)."""
    return httpx.AsyncClient(
        base_url="https://pdbe.test/api", transport=httpx.MockTransport(_handler)
    )
