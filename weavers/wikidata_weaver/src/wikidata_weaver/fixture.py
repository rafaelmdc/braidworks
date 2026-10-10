"""A tiny, deterministic stand-in for the api backend — for offline tests.

A keyless API backend is *always configured*, so golden/order tests would hit the
live Wikidata service. This serves canned SPARQL-results JSON via
``httpx.MockTransport`` so ``build_wikidata_weaver_fixture()`` runs offline and
reproducibly. The canned payload is a real response shape for ``Ursus arctos``.
"""

from __future__ import annotations

import json
from copy import deepcopy
from urllib.parse import unquote_plus

import httpx

# Real Wikidata SPARQL bindings for `?item wdt:P225 "Ursus arctos"` (one item,
# enwiki sitelink, two English vernacular names). ?sname is echoed back.
_URSUS_ARCTOS = {
    "head": {"vars": ["sname", "item", "article", "sitelinks", "vn"]},
    "results": {
        "bindings": [
            {
                "sname": {"type": "literal", "value": "Ursus arctos"},
                "item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q36341"},
                "article": {"type": "uri", "value": "https://en.wikipedia.org/wiki/Brown_bear"},
                "sitelinks": {
                    "type": "literal",
                    "datatype": "http://www.w3.org/2001/XMLSchema#integer",
                    "value": "142",
                },
                "vn": {"xml:lang": "en", "type": "literal", "value": "Brown Bear"},
            },
            {
                "sname": {"type": "literal", "value": "Ursus arctos"},
                "item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q36341"},
                "article": {"type": "uri", "value": "https://en.wikipedia.org/wiki/Brown_bear"},
                "sitelinks": {
                    "type": "literal",
                    "datatype": "http://www.w3.org/2001/XMLSchema#integer",
                    "value": "142",
                },
                "vn": {"xml:lang": "en", "type": "literal", "value": "grizzly bear"},
            },
        ]
    },
}

_EMPTY = {
    "head": {"vars": ["sname", "item", "article", "sitelinks", "vn", "rankLabel"]},
    "results": {"bindings": []},
}

# A cross-code homonym: "Pholidota" is BOTH an orchid genus (botany) and the pangolin
# order (zoology). Both carry P225 "Pholidota", so the name is ambiguous unless the
# caller disambiguates by taxon rank (?rankLabel). Used by the rank-disambiguation test.
_PHOLIDOTA = {
    "head": {"vars": ["sname", "item", "article", "vn", "rankLabel"]},
    "results": {
        "bindings": [
            {
                "sname": {"type": "literal", "value": "Pholidota"},
                "item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q1300407"},
                "article": {
                    "type": "uri",
                    "value": "https://en.wikipedia.org/wiki/Pholidota_(plant)",
                },
                "rankLabel": {"xml:lang": "en", "type": "literal", "value": "genus"},
                "vn": {"xml:lang": "en", "type": "literal", "value": "Pholidota"},
            },
            {
                "sname": {"type": "literal", "value": "Pholidota"},
                "item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q2191516"},
                "article": {"type": "uri", "value": "https://en.wikipedia.org/wiki/Pangolin"},
                "rankLabel": {"xml:lang": "en", "type": "literal", "value": "order"},
                "vn": {"xml:lang": "en", "type": "literal", "value": "pangolin"},
            },
        ]
    },
}


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/api.php"):
        ids = request.url.params.get("ids", "").split("|")
        return httpx.Response(
            200,
            json={
                "entities": {
                    qid: {
                        "id": qid,
                        "labels": {"en": {"language": "en", "value": "brown bear"}},
                        "descriptions": {},
                        "sitelinks": {"enwiki": {"site": "enwiki", "title": "Brown bear"}},
                        "claims": {
                            "P225": [
                                {
                                    "mainsnak": {
                                        "snaktype": "value",
                                        "datavalue": {"value": "Ursus arctos"},
                                    }
                                }
                            ]
                        },
                    }
                    if qid == "Q36341"
                    else {"id": qid, "missing": ""}
                    for qid in ids
                }
            },
        )
    if request.url.path.endswith("/sparql"):
        # The query is POSTed as form data (large batches exceed a GET URL);
        # unquote_plus so "Ursus+arctos" reads back as "Ursus arctos".
        query = request.url.params.get("query", "") + unquote_plus(
            request.content.decode("utf-8", "ignore")
        )
        if "wdt:P685" in query and "9644" in query:
            payload = deepcopy(_URSUS_ARCTOS)
            for row in payload["results"]["bindings"]:
                row["sname"]["value"] = "9644"
        elif "Ursus arctos" in query:
            payload = _URSUS_ARCTOS
        elif "Pholidota" in query:
            payload = _PHOLIDOTA
        else:
            payload = _EMPTY
        return httpx.Response(
            200,
            content=json.dumps(payload),
            headers={"Content-Type": "application/sparql-results+json"},
        )
    return httpx.Response(404, content=json.dumps({"detail": "not found"}))


def mock_client() -> httpx.AsyncClient:
    """An ``httpx.AsyncClient`` serving the canned responses (no network)."""
    return httpx.AsyncClient(
        base_url="https://wikidata.test", transport=httpx.MockTransport(_handler)
    )
