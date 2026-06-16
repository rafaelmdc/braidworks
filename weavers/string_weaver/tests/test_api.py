"""Unit tests for the STRING api backend — edge mapping + deterministic ordering.

Driven by ``httpx.MockTransport`` so they are offline and deterministic. They
exercise: partner/score extraction, the fixed sort (score desc, then name), channel
subscore mapping, skipping nameless edges, empty/blank/error handling.
"""

from __future__ import annotations

import json

import httpx

from string_weaver.backends.api import StringApiBackend

CAP = "list_interactions"
ALL = frozenset(
    {"protein.query", "protein.interaction.partners", "protein.interaction.count",
     "protein.interaction.records"}
)


STRING_ID = "9606.ENSP_TP53"  # the resolved STRING id partners are grouped under


def _edge(name, score, **channels):
    return {"preferredName_A": "TP53", "preferredName_B": name, "stringId_A": STRING_ID,
            "stringId_B": f"id_{name}", "score": score, **channels}


def _backend(payload, *, status=200, calls=None, idmap=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        if status != 200:
            return httpx.Response(status, content=b"{}")
        ids = [i for i in request.url.params.get("identifiers", "").split("\r") if i]
        if request.url.path.endswith("/get_string_ids"):
            rows = [{"queryItem": i, "stringId": (idmap or {}).get(i, STRING_ID)} for i in ids]
            return httpx.Response(200, content=json.dumps(rows))
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
    # the fan dimension: each partner name as a protein.query (chains into uniprot)
    assert v["protein.query"] == ["MDM2", "SFN"]


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


async def test_resolves_batch_in_two_bulk_calls():
    """N accessions -> get_string_ids + interaction_partners (two calls total), with
    partner edges grouped back to each query by stringId_A."""
    payload = [
        _edge("MDM2", 0.99),  # stringId_A = STRING_ID (P04637/TP53)
        {"preferredName_A": "BRCA1", "preferredName_B": "BARD1",
         "stringId_A": "9606.ENSP_BRCA1", "stringId_B": "id_BARD1", "score": 0.9},
    ]
    calls: list[str] = []
    backend = _backend(payload, calls=calls,
                       idmap={"P04637": STRING_ID, "P38398": "9606.ENSP_BRCA1"})
    records = await backend.fetch(
        CAP, [{"protein.uniprot.accession": "P04637"}, {"protein.uniprot.accession": "P38398"}],
        requested_outputs=ALL, groups_to_compute=frozenset(),
    )
    assert [r.found for r in records] == [True, True]
    assert records[0].values["protein.interaction.partners"] == ["MDM2"]
    assert records[1].values["protein.interaction.partners"] == ["BARD1"]
    assert len(calls) == 2  # one get_string_ids + one interaction_partners for the whole batch


def test_fingerprint_is_stable_and_real():
    fp = StringApiBackend().fingerprint()
    assert fp and fp.lower() not in ("", "unknown") and "TODO" not in fp
