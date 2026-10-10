"""Representative evidence keeps genome relation and source provenance explicit."""

import httpx
from braidworks.core import Strand, StrandSet, WeaveStatus
from gtdb_weaver.backends.api import GtdbApiBackend
from gtdb_weaver.factory import build_gtdb_weaver_fixture


async def test_local_representative_does_not_change_taxonomy_or_tree_shape():
    async with build_gtdb_weaver_fixture() as weaver:
        inputs = [StrandSet.from_strands("taxon", [Strand("ncbi.taxon.id", "562")])]
        result = (
            await weaver.execute_batch(
                "describe_gtdb_taxonomy",
                inputs,
                requested_outputs=frozenset({"gtdb.genome.representative", "gtdb.taxon.id"}),
                backend="local",
            )
        )[0]
        assert result.status is WeaveStatus.OK
        values = {s.type_id: s.value for s in result.strands}
        assert values["gtdb.taxon.id"] == "s__Escherichia coli"
        record = values["gtdb.genome.representative"]
        assert record["source_accession"] == "GCA_000005845.2"
        assert record["release"] and record["available"]
        assert "not necessarily" in record["relation"]


async def test_api_nonrepresentative_is_not_presented_as_representative():
    row = {
        "accession": "GCA_000155005.1",
        "isGtdbSpeciesRep": False,
        "gtdbTaxonomy": "d__Bacteria;s__Escherichia coli",
    }
    async with httpx.AsyncClient(
        base_url="https://fixture",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"rows": [row]})),
    ) as client:
        backend = GtdbApiBackend(client=client)
        result = (
            await backend.fetch(
                "describe_gtdb_taxonomy",
                [{"organism.scientific_name": "Escherichia coli"}],
                requested_outputs=frozenset({"gtdb.genome.representative"}),
                groups_to_compute=frozenset({"representative"}),
            )
        )[0]
        record = result.values["gtdb.genome.representative"]
        assert record["source_accession"] is None and record["release"] is None
        assert record["available"] is False
