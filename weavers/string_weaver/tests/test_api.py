"""Unit tests for the STRING api backend — edge mapping + deterministic ordering.

Driven by ``httpx.MockTransport`` so they are offline and deterministic. They
exercise: partner/score extraction, the fixed sort (score desc, then name), channel
subscore mapping, skipping nameless edges, empty/blank/error handling.
"""

from __future__ import annotations

import json

import httpx

from string_weaver.backends.api import StringApiBackend

CAP = "resolve_interactions"
ALL = frozenset(
    {"protein.interaction.partners", "protein.interaction.count", "protein.interaction.records"}
)


def _edge(name, score, **channels):
    return {"preferredName_A": "TP53", "preferredName_B": name, "stringId_B": f"id_{name}",
            "score": score, **channels}


def _backend(payload, *, status=200, calls=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        if status != 200:
            return httpx.Response(status, content=b"{}")
        if request.url.path.endswith("/interaction_partners"):
            return httpx.Response(200, content=json.dumps(payload))
        return httpx.Response(404, content=b"{}")

    client = httpx.AsyncClient(base_url="https://s/api", transport=httpx.MockTransport(handler))
    return StringApiBackend(client=client)


async def _one(backend, accession):
    records = await backend.fetch(
        CAP, [{"protein.uniprot.accession": accession}], requested_outputs=ALL,
        groups_to_compute=frozenset(),
    )
    assert len(records) == 1
    return records[0]


async def test_extracts_partners_count_records():
    record = await _one(_backend([_edge("MDM2", 0.999, escore=0.9), _edge("SFN", 0.95)]), "P04637")
    v = record.values
    assert record.found is True
    assert v["protein.interaction.partners"] == ["MDM2", "SFN"]
    assert v["protein.interaction.count"] == 2
    assert v["protein.interaction.records"][0]["partner"] == "MDM2"
    assert v["protein.interaction.records"][0]["channels"] == {"experimental": 0.9}


async def test_ordering_is_deterministic_score_then_name():
    # Lower-score partner first in the payload; tie broken by name ascending.
    payload = [_edge("ZZZ", 0.5), _edge("AAA", 0.9), _edge("BBB", 0.9)]
    v = (await _one(_backend(payload), "P04637")).values
    assert v["protein.interaction.partners"] == ["AAA", "BBB", "ZZZ"]


async def test_nameless_edge_is_skipped():
    payload = [_edge("MDM2", 0.9), {"preferredName_A": "TP53", "score": 0.8}]
    v = (await _one(_backend(payload), "P04637")).values
    assert v["protein.interaction.partners"] == ["MDM2"]


async def test_empty_list_is_a_miss():
    record = await _one(_backend([]), "P99999")
    assert record.found is False and record.error is None


async def test_blank_accession_makes_no_call():
    calls: list[str] = []
    record = await _one(_backend([], calls=calls), "   ")
    assert record.found is False and record.error is None and calls == []


async def test_unmappable_identifier_404_is_a_miss():
    # STRING 404s an identifier it can't map -> NO_MATCH, not an error.
    record = await _one(_backend([], status=404), "X0X0X0")
    assert record.found is False and record.error is None


async def test_server_error_becomes_per_entity_error():
    record = await _one(_backend([], status=500), "P04637")
    assert record.found is False and record.error is not None and "STRING" in record.error


def test_fingerprint_is_stable_and_real():
    fp = StringApiBackend().fingerprint()
    assert fp and fp.lower() not in ("", "unknown") and "TODO" not in fp
