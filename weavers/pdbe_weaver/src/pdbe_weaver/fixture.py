"""A tiny, deterministic PDBe stand-in for ``weaverkit verify --strict`` golden.

The api backend is *always configured* (PDBe needs no key), so golden would otherwise
hit the live service. This module serves a canned ``best_structures`` response for
P04637 with **two distinct structures and a duplicate chain of one** (so the dedup +
best-chain path is exercised), shaped like real PDBe rows
(``pdb_id``/``experimental_method``/``resolution``/``coverage``). It also serves a
``/pdb/entry/summary/{id}`` detail object for ``1tup`` (describe_structure golden).
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

# One PDB entry summary (describe_structure), shaped like real /pdb/entry/summary/1tup.
_STRUCTURE_DETAIL = {
    "1tup": {
        "title": "TUMOR SUPPRESSOR P53 COMPLEXED WITH DNA",
        "experimental_method": ["X-ray diffraction"],
        "release_date": "19950711",
        "deposition_date": "19950711",
        "entry_authors": ["Cho, Y.", "Gorina, S.", "Jeffrey, P.D.", "Pavletich, N.P."],
    }
}


def _handler(request: httpx.Request) -> httpx.Response:
    if "/best_structures/" in request.url.path:
        acc = request.url.path.rsplit("/", 1)[1]
        if acc in _BEST_STRUCTURES:
            return httpx.Response(200, content=json.dumps({acc: _BEST_STRUCTURES[acc]}))
        return httpx.Response(404, content=json.dumps({"detail": "no structures"}))
    if "/pdb/entry/summary" in request.url.path:
        # bulk POST: ids arrive comma-separated in the body (fall back to the path id).
        body = request.content.decode() if request.content else request.url.path.rsplit("/", 1)[1]
        ids = [p.strip() for p in body.split(",") if p.strip()]
        found = {p: [_STRUCTURE_DETAIL[p]] for p in ids if p in _STRUCTURE_DETAIL}
        return httpx.Response(200, content=json.dumps(found))
    return httpx.Response(404, content=json.dumps({"detail": "not found"}))


def mock_client() -> httpx.AsyncClient:
    """An ``httpx.AsyncClient`` serving the canned PDBe responses (no network)."""
    return httpx.AsyncClient(
        base_url="https://pdbe.test/api", transport=httpx.MockTransport(_handler)
    )
