"""Many-to-many reference mappings preserve exact provider accession evidence."""

from copy import deepcopy

import httpx
from bacdive_weaver.backends.api import BacdiveApiBackend
from bacdive_weaver.fixture import _TYPE_STRAIN
from bacdive_weaver.identifiers import collection_id, project_identifiers


async def test_reference_mapping_retains_multiplicity_deduplicates_and_no_fallback():
    calls = []

    def handle(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"results": [3, 2, 3], "next": None})

    async with httpx.AsyncClient(
        base_url="https://test/v2", transport=httpx.MockTransport(handle)
    ) as client:
        backend = BacdiveApiBackend(client=client)
        records = await backend.fetch(
            "map_to_strain",
            [
                {"culture.collection.id": "dsm   2801"},
                {"culture.collection.id": "DSM 2801"},
                {"genome.accession": "GCA_000243275.1"},
                {"culture.collection.id": "bad", "genome.accession": "GCA_000243275"},
            ],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"strains"}),
        )
        assert len(calls) == 2
        assert records[0].values["microbe.bacdive.strain_id"] == [2, 3]
        assert any("GCA_000243275.1" in path for path in calls)
        assert records[2].values["microbe.bacdive.strain_coverage"]["input"] == "GCA_000243275.1"
        records[0].values["microbe.bacdive.strain_id"].append(4)
        assert records[1].values["microbe.bacdive.strain_id"] == [2, 3]
        assert not records[3].found


async def test_reverse_mapping_bulk_fetch_and_unknown_reference_retention():
    record = deepcopy(_TYPE_STRAIN)
    record["Literature"] = {
        "culture collection no.": "DSM 2801, ATCC 4651, undecodable (reference)"
    }
    record["Sequence information"] = {
        "Genome sequences": [
            {"INSDC accession": "GCA_000243275"},
            {"INSDC accession": "GCF_000243275.2"},
        ]
    }
    calls = []

    def handle(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"results": {"2": record, "3": record}})

    async with httpx.AsyncClient(
        base_url="https://test/v2", transport=httpx.MockTransport(handle)
    ) as client:
        results = await BacdiveApiBackend(client=client).fetch(
            "map_from_strain",
            [{"microbe.bacdive.strain_id": 2}, {"microbe.bacdive.strain_id": 3}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"identifiers"}),
        )
    assert len(calls) == 1 and calls[0].endswith("/fetch/2;3")
    assert results[0].values["culture.collection.id"] == ["ATCC 4651", "DSM 2801"]
    assert results[0].values["genome.accession"] == ["GCA_000243275", "GCF_000243275.2"]
    assert results[0].values["microbe.bacdive.identifier_evidence"]["unparsed_references"] == [
        "undecodable (reference)"
    ]


def test_identifier_normalization_does_not_guess_aliases_or_versions():
    assert collection_id("DSM 002801") == "DSM 002801"
    assert collection_id("DSM2801") is None
    assert project_identifiers({})["genome.accession"] == []
