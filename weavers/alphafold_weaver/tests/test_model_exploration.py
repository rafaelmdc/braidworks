"""Model identities drill exactly; enumeration never changes representative selection."""

import httpx
from alphafold_weaver.backends.api import AlphafoldApiBackend
from alphafold_weaver.factory import build_alphafold_weaver_fixture
from braidworks.core import Strand, StrandSet, WeaveStatus


async def test_listed_model_can_be_described_exactly():
    async with build_alphafold_weaver_fixture() as weaver:
        inputs = [
            StrandSet.from_strands("protein", [Strand("protein.uniprot.accession", "P04637")])
        ]
        result = (
            await weaver.execute_batch(
                "list_models",
                inputs,
                requested_outputs=frozenset({"structure.alphafold.model_id"}),
                backend="api",
            )
        )[0]
        assert result.status is WeaveStatus.OK
        ids = next(s.value for s in result.strands if s.type_id == "structure.alphafold.model_id")
        assert ids == ["AF-P04637-2-F1@v6", "AF-P04637-F1@v6"]
        queried = [
            StrandSet.from_strands(value, [Strand("structure.alphafold.model_id", value)])
            for value in ids
        ]
        described = await weaver.execute_batch(
            "describe_prediction",
            queried,
            requested_outputs=frozenset({"structure.alphafold.entry_id"}),
            backend="api",
        )
        assert [r.strands[0].value for r in described] == ["AF-P04637-2-F1", "AF-P04637-F1"]


async def test_model_fan_is_full_while_display_is_capped():
    rows = [{"entryId": f"AF-P04637-F{i}", "latestVersion": 6} for i in range(1, 13)]
    rows.append(dict(rows[0]))
    client = httpx.AsyncClient(
        base_url="https://fixture",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=list(reversed(rows)))
        ),
    )
    async with client:
        backend = AlphafoldApiBackend(client=client)
        record = (
            await backend.fetch(
                "list_models",
                [{"protein.uniprot.accession": "P04637"}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset(),
            )
        )[0]
        assert len(record.values["structure.alphafold.model_id"]) == 12
        assert len(record.values["structure.alphafold.models"]) == 10
        assert record.values["structure.alphafold.model_coverage"]["source_complete"] is None


async def test_version_mismatch_never_silently_upgrades():
    async with build_alphafold_weaver_fixture() as weaver:
        inputs = [
            StrandSet.from_strands(
                "model", [Strand("structure.alphafold.model_id", "AF-P04637-F1@v5")]
            )
        ]
        result = (
            await weaver.execute_batch(
                "describe_prediction",
                inputs,
                requested_outputs=frozenset({"structure.alphafold.entry_id"}),
                backend="api",
            )
        )[0]
        assert result.status is WeaveStatus.ERROR
        assert not result.strands
