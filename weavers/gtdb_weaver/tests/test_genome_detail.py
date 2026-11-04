"""Genome-specific metrics and release history are not species-wide claims."""

import httpx
import pytest
from gtdb_weaver.backends.api import GtdbApiBackend
from gtdb_weaver.genome_detail import GenomeFormatError, project_card, project_history

CARD = {
    "genome": {"accession": "GCA_000005845.2", "name": "GCF_000005845.2"},
    "metadata_gene": {"checkm_completeness": 99.97, "checkm2_completeness": 100.0},
    "metadata_nucleotide": {"genome_size": 4641652},
    "metadataTaxonomy": {"synonyms": None},
}


def test_history_keeps_release_classifications_separate():
    result = project_history(
        [{"release": "R95", "s": "s__Old name"}, {"release": "R232", "s": "s__New name"}],
        "GCF_000005845.2",
    )
    assert [row["release"] for row in result["records"]] == ["R232", "R95"]
    assert project_card(CARD, "GCF_000005845.2")["gtdb.genome.synonyms"]["synonyms"] is None
    with pytest.raises(GenomeFormatError, match="Conflicting"):
        project_history([{"release": "R232", "s": "a"}, {"release": "R232", "s": "b"}], "a")
    with pytest.raises(GenomeFormatError, match="identity"):
        project_card(CARD, "GCF_999999999.1")


async def test_repeated_genomes_share_requests_detach_and_keep_version():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(
            200,
            json=CARD
            if request.url.path.endswith("/card")
            else [{"release": "R232", "s": "s__New name"}],
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://test"
    ) as client:
        backend = GtdbApiBackend(client=client)
        results = await backend.fetch(
            "describe_genome",
            [{"genome.accession": "GCF_000005845.2"}] * 2,
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"history", "quality"}),
        )
    assert len(calls) == 2 and all("GCF_000005845.2" in call for call in calls)
    results[0].values["gtdb.genome.history"]["records"].clear()
    assert results[1].values["gtdb.genome.history"]["records"]
    assert results[1].values["gtdb.genome.quality"]["gene"]["checkm2_completeness"] == 100.0


async def test_missing_history_keeps_known_genome_identity():
    def handler(request):
        return (
            httpx.Response(200, json=CARD)
            if request.url.path.endswith("/card")
            else httpx.Response(404)
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://test"
    ) as client:
        backend = GtdbApiBackend(client=client)
        result = (
            await backend.fetch(
                "describe_genome",
                [{"genome.accession": "GCF_000005845.2"}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset({"history"}),
            )
        )[0]
    assert result.found and not result.error
    assert result.values["gtdb.genome.history"]["available"] is False
    assert result.values["gtdb.genome.history"]["records"] is None
