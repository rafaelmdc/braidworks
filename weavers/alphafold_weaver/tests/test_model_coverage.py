"""A preferred F1 ID never substitutes for observed sequence coverage."""

import httpx
import pytest
from alphafold_weaver.backends.api import AlphafoldApiBackend, _coverage


async def test_long_protein_f1_retains_partial_range_and_warning():
    entry = {
        "entryId": "AF-LONG-F1",
        "uniprotStart": 1,
        "uniprotEnd": 1400,
        "uniprotSequence": "A" * 4000,
    }
    async with httpx.AsyncClient(
        base_url="https://fixture",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=[entry])),
    ) as client:
        record = (
            await AlphafoldApiBackend(client=client).fetch(
                "describe_model",
                [{"protein.uniprot.accession": "LONG"}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset(),
            )
        )[0]
    coverage = record.values["structure.alphafold.records"]["coverage"]
    assert coverage == {
        "uniprot_start": 1,
        "uniprot_end": 1400,
        "sequence_length": 4000,
        "model_length": 1400,
        "fragment_number": 1,
        "status": "partial",
    }
    assert record.found and record.warnings


def test_full_and_unavailable_coverage_are_distinct():
    assert (
        _coverage(
            {"entryId": "AF-S-F1", "uniprotStart": 1, "uniprotEnd": 3, "uniprotSequence": "AAA"}
        )["status"]
        == "full_sequence"
    )
    assert _coverage({"entryId": "AF-S-F1"})["status"] == "unknown"


@pytest.mark.parametrize("start,end", [(0, 3), (True, 3), (4, 3), (1, 5)])
async def test_invalid_coverage_is_an_error_value(start, end):
    entry = {
        "entryId": "AF-S-F1",
        "uniprotStart": start,
        "uniprotEnd": end,
        "uniprotSequence": "AAA",
    }
    async with httpx.AsyncClient(
        base_url="https://fixture",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=[entry])),
    ) as client:
        record = (
            await AlphafoldApiBackend(client=client).fetch(
                "describe_model",
                [{"protein.uniprot.accession": "S"}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset(),
            )
        )[0]
    assert record.error and not record.found
