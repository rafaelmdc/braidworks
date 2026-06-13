"""A tiny, deterministic UniProtKB stand-in for ``weaverkit verify --strict`` golden.

The api backend is *always configured* (UniProtKB REST needs no key), so golden
would otherwise hit the live service — flaky and non-reproducible. This module
serves a canned ``/uniprotkb/search`` response for one query ("TP53") whose top hit
is human p53 (P04637), carrying every field the mapper reads. The shape mirrors a
real reviewed entry (nested proteinDescription, genes, organism.taxonId, a FUNCTION
comment, sequence.length) so the mapping path is exercised exactly as in production.
``build_uniprot_weaver_fixture()`` (in factory.py) wires the backend to this transport.
"""

from __future__ import annotations

import json

import httpx

# A real-shaped reviewed (Swiss-Prot) entry for human TP53.
_TP53 = {
    "entryType": "UniProtKB reviewed (Swiss-Prot)",
    "primaryAccession": "P04637",
    "uniProtkbId": "P53_HUMAN",
    "organism": {"scientificName": "Homo sapiens", "taxonId": 9606},
    "annotationScore": 5.0,
    "proteinDescription": {
        "recommendedName": {"fullName": {"value": "Cellular tumor antigen p53"}}
    },
    "genes": [{"geneName": {"value": "TP53"}}],
    "comments": [
        {
            "commentType": "FUNCTION",
            "texts": [
                {
                    "value": (
                        "Multifunctional transcription factor that induces cell cycle "
                        "arrest, DNA repair or apoptosis upon binding to its target DNA "
                        "sequence (PubMed:11025664). Acts as a tumor suppressor."
                    )
                }
            ],
        }
    ],
    "sequence": {"length": 393},
}


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/uniprotkb/search"):
        query = request.url.params.get("query", "")
        # Only "TP53" resolves; anything else is a clean empty result (NO_MATCH).
        results = [_TP53] if "TP53" in query else []
        return httpx.Response(200, content=json.dumps({"results": results}))
    return httpx.Response(404, content=json.dumps({"detail": "not found"}))


def mock_client() -> httpx.AsyncClient:
    """An ``httpx.AsyncClient`` serving the canned UniProt responses (no network)."""
    return httpx.AsyncClient(
        base_url="https://uniprot.test", transport=httpx.MockTransport(_handler)
    )
