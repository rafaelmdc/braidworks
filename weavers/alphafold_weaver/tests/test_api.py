"""Unit tests for the AlphaFold api backend — canonical-model pick + mapping.

Driven by ``httpx.MockTransport`` so they are offline and deterministic. They
exercise: picking the canonical model over isoforms, the lowest-entry-id fallback,
field extraction, and 404/empty/blank/error handling.
"""

from __future__ import annotations

import json

import httpx

from alphafold_weaver.backends.api import AlphafoldApiBackend

CAP = "describe_model"
ALL = frozenset(
    {"structure.alphafold.entry_id", "structure.alphafold.mean_plddt",
     "structure.alphafold.model_url", "structure.alphafold.pae_image_url",
     "structure.alphafold.version", "structure.alphafold.records"}
)


def _entry(entry_id, plddt=80.0, **extra):
    return {"entryId": entry_id, "globalMetricValue": plddt, "latestVersion": 6,
            "pdbUrl": f"https://af/files/{entry_id}.pdb",
            "paeImageUrl": f"https://af/files/{entry_id}-pae.png", **extra}


def _backend(entries=None, *, status=200, calls=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        if status != 200:
            return httpx.Response(status, content=b"{}")
        if "/api/prediction/" in request.url.path:
            return httpx.Response(200, content=json.dumps(entries if entries is not None else []))
        return httpx.Response(404, content=b"{}")

    client = httpx.AsyncClient(base_url="https://af", transport=httpx.MockTransport(handler))
    return AlphafoldApiBackend(client=client)


async def _one(backend, accession):
    records = await backend.fetch(
        CAP, [{"protein.uniprot.accession": accession}], requested_outputs=ALL,
        groups_to_compute=frozenset(),
    )
    assert len(records) == 1
    return records[0]


async def test_picks_canonical_over_isoform():
    entries = [_entry("AF-P04637-2-F1", 76.9), _entry("AF-P04637-F1", 75.06,
               fractionPlddtVeryHigh=0.34)]
    v = (await _one(_backend(entries), "P04637")).values
    assert v["structure.alphafold.entry_id"] == "AF-P04637-F1"  # canonical, not the isoform
    assert v["structure.alphafold.mean_plddt"] == 75.06
    assert v["structure.alphafold.version"] == 6
    assert v["structure.alphafold.model_url"].endswith("AF-P04637-F1.pdb")
    assert v["structure.alphafold.records"]["plddt"]["very_high"] == 0.34


async def test_falls_back_to_lowest_entry_id_without_canonical():
    # No AF-Q-F1 canonical present -> deterministic lowest entry id.
    entries = [_entry("AF-Q-3-F1"), _entry("AF-Q-2-F1")]
    v = (await _one(_backend(entries), "Q")).values
    assert v["structure.alphafold.entry_id"] == "AF-Q-2-F1"


async def test_400_and_404_are_misses():
    # AlphaFold 400s a malformed accession and 404s when there's no model — both NO_MATCH.
    for status in (400, 404):
        record = await _one(_backend(status=status), "bad")
        assert record.found is False and record.error is None


async def test_empty_list_is_a_miss():
    record = await _one(_backend([]), "P99999")
    assert record.found is False and record.error is None


async def test_blank_accession_makes_no_call():
    calls: list[str] = []
    record = await _one(_backend(calls=calls), "   ")
    assert record.found is False and record.error is None and calls == []


async def test_server_error_becomes_per_entity_error():
    record = await _one(_backend(status=500), "P04637")
    assert record.found is False and record.error is not None and "AlphaFold" in record.error


def test_fingerprint_is_stable_and_real():
    fp = AlphafoldApiBackend().fingerprint()
    assert fp and fp.lower() not in ("", "unknown") and "TODO" not in fp
