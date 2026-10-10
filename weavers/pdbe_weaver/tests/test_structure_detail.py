"""Source numbering, acquisition limits and bulk detail requests."""

import gzip

import httpx
import pytest
from pdbe_weaver.backends.api import PdbeApiBackend
from pdbe_weaver.structure_detail import DetailFormatError, sifts_residues

XML = b"""<entry xmlns="http://www.ebi.ac.uk/pdbe/docs/sifts/eFamily.xsd" dbAccessionId="1cbs"><entity entityId="A" type="protein"><segment segId="s"><listResidue><residue dbResNum="10"><crossRefDb dbSource="PDB" dbResNum="-1A" dbChainId="A"/><crossRefDb dbSource="UniProt" dbResNum="2" dbAccessionId="P29373"/><residueDetail property="Annotation">Not_Observed</residueDetail></residue></listResidue></segment></entity></entry>"""


def test_full_residue_projection_preserves_author_numbering_and_unobserved():
    result = sifts_residues(gzip.compress(XML), "1cbs", "https://test")
    row = result["records"][0]
    assert row["cross_references"][0]["dbResNum"] == "-1A"
    assert row["cross_references"][1]["dbResNum"] == "2"
    assert row["annotations"][0]["text"] == "Not_Observed"
    with pytest.raises(DetailFormatError, match="identity"):
        sifts_residues(gzip.compress(XML), "2xyz", "https://test")


async def test_entity_detail_batches_many_into_one_request():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        ids = request.content.decode().split(",")
        if request.url.path.endswith("/summary"):
            return httpx.Response(200, json={pid: [{"title": "test"}] for pid in ids})
        assert request.url.path.endswith("/molecules")
        return httpx.Response(
            200,
            json={
                pid: [{"entity_id": 1, "in_chains": ["A"], "in_struct_asyms": ["X"]}] for pid in ids
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://test"
    ) as client:
        backend = PdbeApiBackend(client=client)
        results = await backend.fetch(
            "describe_structure",
            [{"pdb.id": "1cbs"}, {"pdb.id": "2xyz"}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"entities"}),
        )
    assert calls == ["/pdb/entry/summary", "/pdb/entry/molecules"]
    assert all(
        result.values["structure.pdb.entities"]["records"][0]["in_struct_asyms"] == ["X"]
        for result in results
    )
