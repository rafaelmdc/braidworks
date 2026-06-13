"""A tiny, deterministic AlphaFold stand-in for ``weaverkit verify --strict`` golden.

The api backend is *always configured* (AlphaFold DB needs no key), so golden would
otherwise hit the live service. This module serves a canned ``prediction`` response for
P04637 with the **canonical model plus one isoform model** (so the canonical-pick path is
exercised), shaped like real AlphaFold entries (``entryId``/``globalMetricValue``/
``pdbUrl``/``paeImageUrl``/pLDDT fractions). ``build_alphafold_weaver_fixture()`` (in
factory.py) wires the backend to this transport.
"""

from __future__ import annotations

import json

import httpx

_PREDICTIONS = {
    "P04637": [
        # an isoform model listed first -> must NOT be picked over the canonical one
        {
            "entryId": "AF-P04637-2-F1",
            "uniprotAccession": "P04637",
            "latestVersion": 6,
            "globalMetricValue": 76.94,
            "pdbUrl": "https://alphafold.ebi.ac.uk/files/AF-P04637-2-F1-model_v6.pdb",
            "paeImageUrl": "https://alphafold.ebi.ac.uk/files/AF-P04637-2-F1-pae_v6.png",
        },
        {
            "entryId": "AF-P04637-F1",
            "uniprotAccession": "P04637",
            "latestVersion": 6,
            "globalMetricValue": 75.06,
            "fractionPlddtVeryHigh": 0.34,
            "fractionPlddtConfident": 0.18,
            "fractionPlddtLow": 0.14,
            "fractionPlddtVeryLow": 0.34,
            "pdbUrl": "https://alphafold.ebi.ac.uk/files/AF-P04637-F1-model_v6.pdb",
            "paeImageUrl": "https://alphafold.ebi.ac.uk/files/AF-P04637-F1-pae_v6.png",
        },
    ]
}


def _handler(request: httpx.Request) -> httpx.Response:
    if "/api/prediction/" in request.url.path:
        acc = request.url.path.rsplit("/", 1)[1]
        if acc in _PREDICTIONS:
            return httpx.Response(200, content=json.dumps(_PREDICTIONS[acc]))
        return httpx.Response(404, content=json.dumps({"detail": "no model"}))
    return httpx.Response(404, content=json.dumps({"detail": "not found"}))


def mock_client() -> httpx.AsyncClient:
    """An ``httpx.AsyncClient`` serving the canned AlphaFold responses (no network)."""
    return httpx.AsyncClient(
        base_url="https://alphafold.test", transport=httpx.MockTransport(_handler)
    )
