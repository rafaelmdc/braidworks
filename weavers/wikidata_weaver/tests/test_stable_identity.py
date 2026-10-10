"""Exact stable identities retain ambiguity and keep English Wikipedia routing."""

from copy import deepcopy

import httpx
import pytest
from braidworks.core import MatchStatus, Strand, StrandSet, WeaveStatus
from wikidata_weaver.backends.api import WikidataApiBackend
from wikidata_weaver.entities import InvalidEntityResponse, entity_records
from wikidata_weaver.fixture import _URSUS_ARCTOS
from wikidata_weaver.weaver import WikidataWeaver

ENTITY = {
    "id": "Q36341",
    "labels": {
        "pt": {"language": "pt", "value": "Urso-pardo"},
        "en": {"language": "en", "value": "brown bear"},
    },
    "descriptions": {"en": {"language": "en", "value": "bear species"}},
    "sitelinks": {
        "enwiki": {"site": "enwiki", "title": "Brown bear"},
        "ptwiki": {"site": "ptwiki", "title": "Urso-pardo"},
    },
    "claims": {
        "P225": [{"mainsnak": {"snaktype": "value", "datavalue": {"value": "Ursus arctos"}}}]
    },
}


def test_redirect_missing_and_explicit_label_fallback():
    body = {
        "redirects": [{"from": "Q1", "to": "Q36341"}],
        "entities": {"Q36341": ENTITY, "Q2": {"id": "Q2", "missing": ""}},
    }
    records = entity_records(body, ["Q1", "Q2"], "pt")
    assert records["Q1"].values["wikidata.identity"]["current_qid"] == "Q36341"
    localized = records["Q1"].values["wikidata.localized"]
    assert localized["label_language"] == "pt" and localized["description_language"] == "en"
    assert records["Q1"].values["wikipedia.title"] == "Brown_bear"
    assert records["Q1"].values["wikidata.sitelinks"] == 2
    assert not records["Q2"].found
    with pytest.raises(InvalidEntityResponse):
        entity_records({"entities": {"Q36341": ENTITY}}, ["Q999"], "pt")


async def test_qid_batch_uses_lookup_mapper_and_detaches_duplicates():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"entities": {"Q36341": ENTITY}})

    async with httpx.AsyncClient(
        base_url="https://fixture", transport=httpx.MockTransport(handler)
    ) as client:
        backend = WikidataApiBackend(client=client)
        async with WikidataWeaver({"api": backend}) as weaver:
            results = await weaver.execute_batch(
                "describe_taxon",
                [
                    StrandSet.from_strands(str(i), [Strand("wikidata.qid", "Q36341")])
                    for i in range(3)
                ],
                requested_outputs=frozenset({"wikidata.localized", "wikipedia.title"}),
                backend="api",
                params={"language": "pt"},
            )
            assert len(calls) == 1 and calls[0].url.params["ids"] == "Q36341"
            assert all(result.status is WeaveStatus.OK for result in results)
            values = [{s.type_id: s.value for s in result.strands} for result in results]
            assert values[0]["wikidata.localized"]["label"] == "Urso-pardo"
            assert values[0]["wikipedia.title"] == "Brown_bear"
            values[0]["wikidata.localized"]["label"] = "mutated"
            assert values[1]["wikidata.localized"]["label"] == "Urso-pardo"


async def test_taxid_duplicates_are_ambiguous_and_invalid_taxid_never_interpolates():
    calls = []

    def handler(request):
        calls.append(request)
        payload = deepcopy(_URSUS_ARCTOS)
        for row in payload["results"]["bindings"]:
            row["sname"]["value"] = "9644"
        extra = deepcopy(payload["results"]["bindings"][0])
        extra["item"]["value"] = "http://www.wikidata.org/entity/Q999"
        payload["results"]["bindings"].append(extra)
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(
        base_url="https://fixture", transport=httpx.MockTransport(handler)
    ) as client:
        backend = WikidataApiBackend(client=client)
        records = await backend.fetch(
            "map_from_taxid",
            [{"ncbi.taxon.id": 9644}, {"ncbi.taxon.id": "9644} UNION {?s ?p ?o}"}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
        assert len(calls) == 1 and b"P685" in calls[0].content
        assert b"UNION%20%7B%3Fs" not in calls[0].content
        assert records[0].status is MatchStatus.AMBIGUOUS and len(records[0].candidates) == 2
        assert records[1].status is MatchStatus.NO_MATCH
