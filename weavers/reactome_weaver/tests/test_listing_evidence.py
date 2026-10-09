"""Listing identity preserves source evidence; conflicts never depend on row order."""

from itertools import permutations

import httpx
import pytest
from reactome_weaver.backends.api import ReactomeApiBackend


async def lookup(rows):
    async with httpx.AsyncClient(
        base_url="https://fixture",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=rows)),
    ) as client:
        return (
            await ReactomeApiBackend(client=client).fetch(
                "list_pathways",
                [{"protein.uniprot.accession": "P04637"}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset(),
            )
        )[0]


async def test_observed_listing_evidence_retained_without_inventing_release():
    row = {
        "stId": "R-HSA-1",
        "displayName": "One",
        "speciesName": "Homo sapiens",
        "isInDisease": False,
        "isInferred": True,
        "sourceExtra": "retained",
    }
    result = await lookup([row, row])
    record = result.values["pathway.reactome.records"][0]
    assert record["species"] == "Homo sapiens" and record["is_inferred"] is True
    assert record["source"] == row
    assert "release" not in record["source"]


@pytest.mark.parametrize(
    "field,value", [("displayName", "Other"), ("speciesName", "Mouse"), ("isInferred", True)]
)
async def test_conflicting_identity_fails_independently_of_order(field, value):
    row = {
        "stId": "R-HSA-1",
        "displayName": "One",
        "speciesName": "Homo sapiens",
        "isInferred": False,
    }
    for rows in permutations([row, {**row, field: value}]):
        result = await lookup(list(rows))
        assert result.error and "Conflicting Reactome" in result.error
        assert not result.found
