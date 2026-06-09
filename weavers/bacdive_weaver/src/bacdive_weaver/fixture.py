"""A tiny, deterministic BacDive stand-in for ``weaverkit verify --strict`` golden.

The api backend is *always configured* (the v2 API needs no key), so golden would
otherwise run against the live service — flaky and non-reproducible. This module
provides an ``httpx.MockTransport`` that serves canned ``taxon`` + ``fetch``
responses for one species (*Escherichia coli*) whose type strain carries the
phenotype fields the golden example asserts. ``build_bacdive_weaver_fixture()``
(in factory.py) wires the api backend to a client using this transport.

The canned record shapes mirror real BacDive v2 records (nested sections, the
``type strain`` flag, dict-or-list subfields) so the mapping path is exercised
exactly as in production.
"""

from __future__ import annotations

import json

import httpx

# Two strains for Escherichia coli; only the second is the type strain.
_TAXON = {"count": 2, "next": None, "previous": None, "results": [1, 2]}

_NON_TYPE_STRAIN = {
    "Name and taxonomic classification": {"genus": "Escherichia", "type strain": "no"},
    "Morphology": {"cell morphology": {"gram stain": "negative", "cell shape": "rod-shaped"}},
}

_TYPE_STRAIN = {
    "General": {"NCBI tax id": {"NCBI tax id": 562}},
    "Name and taxonomic classification": {"genus": "Escherichia", "type strain": "yes"},
    "Morphology": {
        "cell morphology": {
            "gram stain": "negative",
            "cell shape": "rod-shaped",
            "motility": "yes",
        }
    },
    "Physiology and metabolism": {
        "oxygen tolerance": {"oxygen tolerance": "facultative anaerobe"}
    },
    "Culture and growth conditions": {
        "culture temp": [
            {"growth": "positive", "type": "optimum", "temperature": "37"},
            {"growth": "positive", "type": "range", "temperature": "10-41"},
        ]
    },
}

_RECORDS = {1: _NON_TYPE_STRAIN, 2: _TYPE_STRAIN}


_EMPTY_TAXON = {"count": 0, "next": None, "previous": None, "results": []}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/taxon/Escherichia/coli"):
        return httpx.Response(200, content=json.dumps(_TAXON))
    if "/taxon/" in path:  # any other species: a clean empty result (NO_MATCH)
        return httpx.Response(200, content=json.dumps(_EMPTY_TAXON))
    if "/fetch/" in path:
        ids = [int(i) for i in path.rsplit("/", 1)[1].split(";") if i]
        results = {str(i): _RECORDS[i] for i in ids if i in _RECORDS}
        return httpx.Response(200, content=json.dumps({"results": results}))
    return httpx.Response(404, content=json.dumps({"detail": "not found"}))


def mock_client() -> httpx.AsyncClient:
    """An ``httpx.AsyncClient`` serving the canned BacDive responses (no network)."""
    return httpx.AsyncClient(
        base_url="https://bacdive.test/v2", transport=httpx.MockTransport(_handler)
    )
