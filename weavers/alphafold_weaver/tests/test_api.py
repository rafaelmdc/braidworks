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
    {
        "structure.alphafold.entry_id",
        "structure.alphafold.mean_plddt",
        "structure.alphafold.model_url",
        "structure.alphafold.pae_image_url",
        "structure.alphafold.version",
        "structure.alphafold.records",
    }
)


def _entry(entry_id, plddt=80.0, **extra):
    return {
        "entryId": entry_id,
        "globalMetricValue": plddt,
        "latestVersion": 6,
        "pdbUrl": f"https://af/files/{entry_id}.pdb",
        "paeImageUrl": f"https://af/files/{entry_id}-pae.png",
        **extra,
    }


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
        CAP,
        [{"protein.uniprot.accession": accession}],
        requested_outputs=ALL,
        groups_to_compute=frozenset(),
    )
    assert len(records) == 1
    return records[0]


async def test_picks_canonical_over_isoform():
    entries = [
        _entry("AF-P04637-2-F1", 76.9),
        _entry("AF-P04637-F1", 75.06, fractionPlddtVeryHigh=0.34),
    ]
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


async def test_lookup_batch_is_bounded_concurrent_and_keeps_query_order():
    import asyncio

    accessions = [f"P{i:05d}" for i in range(6)]
    active = peak = calls = 0

    async def handler(request):
        nonlocal active, peak, calls
        accession = request.url.path.rsplit("/", 1)[-1]
        active += 1
        peak = max(peak, active)
        calls += 1
        try:
            await asyncio.sleep(0.02 if accession == accessions[0] else 0.001)
            if accession == accessions[3]:
                return httpx.Response(503, json={})
            return httpx.Response(200, json=[_entry("AF-" + accession + "-F1")])
        finally:
            active -= 1

    backend = AlphafoldApiBackend(
        client=httpx.AsyncClient(
            base_url="https://fixture",
            transport=httpx.MockTransport(handler),
        ),
        max_concurrency=2,
    )
    queries = [{"protein.uniprot.accession": accession} for accession in accessions]
    records = await backend.fetch(
        CAP,
        queries,
        requested_outputs=ALL,
        groups_to_compute=frozenset(),
    )
    assert peak == 2 and active == 0 and calls == len(queries)
    assert [record.query for record in records] == queries
    for accession, record in zip(accessions, records):
        if accession == accessions[3]:
            assert record.error and not record.found
        else:
            assert (
                record.found
                and record.values["structure.alphafold.entry_id"] == "AF-" + accession + "-F1"
            )


async def test_confidence_references_are_requested_and_do_not_download():
    calls = []
    backend = _backend(
        [
            _entry(
                "AF-P04637-F1", paeDocUrl="https://af/pae.json", plddtDocUrl="https://af/plddt.json"
            )
        ],
        calls=calls,
    )
    query = {"protein.uniprot.accession": "P04637"}
    default = (
        await backend.fetch(CAP, [query], requested_outputs=ALL, groups_to_compute=frozenset())
    )[0]
    assert "structure.alphafold.confidence" not in default.values
    record = (
        await backend.fetch(
            CAP,
            [query],
            requested_outputs=frozenset({"structure.alphafold.confidence"}),
            groups_to_compute=frozenset({"confidence"}),
        )
    )[0]
    confidence = record.values["structure.alphafold.confidence"]
    assert confidence["pae_json_url"] == "https://af/pae.json"
    assert confidence["plddt_json_url"] == "https://af/plddt.json"
    assert confidence["entry_id"] == "AF-P04637-F1" and confidence["version"] == 6
    assert len(calls) == 2 and all("/api/prediction/" in call for call in calls)
    await backend.aclose()


async def test_missing_confidence_references_are_not_guessed():
    backend = _backend([_entry("AF-P04637-F1")])
    record = (
        await backend.fetch(
            CAP,
            [{"protein.uniprot.accession": "P04637"}],
            requested_outputs=frozenset({"structure.alphafold.confidence"}),
            groups_to_compute=frozenset({"confidence"}),
        )
    )[0]
    assert record.values["structure.alphafold.confidence"]["pae_json_url"] is None
    assert record.values["structure.alphafold.confidence"]["plddt_json_url"] is None
    await backend.aclose()
