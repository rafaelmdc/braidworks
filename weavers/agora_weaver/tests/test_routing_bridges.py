"""Genome and reaction fan keys retain exact source model membership."""

import sqlite3

from agora_weaver import dataset
from agora_weaver.backends.local import AgoraLocalBackend
from agora_weaver.fixture import fixture_reaction_db_path

MODEL = "AGORA2-v2.01:Abiotrophia_defectiva_ATCC_49176"


async def test_exact_genome_bridge_and_model_genomes_do_not_acquire(tmp_path):
    backend = AgoraLocalBackend(reaction_db_path=tmp_path / "missing.sqlite")
    records = await backend.fetch(
        "list_reconstructions",
        [
            {"genome.accession": "GCF_000160075.2"},
            {"genome.accession": "GCF_000160075", "ncbi.taxon.id": 592010},
        ],
        requested_outputs=frozenset(),
        groups_to_compute=frozenset({"reconstructions"}),
    )
    assert records[0].values["microbe.agora.reconstruction_id"] == [MODEL]
    assert not records[1].found
    genomes = (
        await backend.fetch(
            "list_genomes",
            [{"microbe.agora.reconstruction_id": MODEL}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"genomes"}),
        )
    )[0]
    assert genomes.values["genome.accession"] == ["GCF_000160075.2"]
    assert not list(tmp_path.iterdir())
    assert dataset.reconstructions_for_genome("GCA_000160075.2") == []


async def test_reaction_pair_is_drillable_and_full_fan_independent_of_display(tmp_path):
    import shutil

    path = tmp_path / "reactions.sqlite"
    shutil.copyfile(fixture_reaction_db_path(), path)
    rid = MODEL.split(":", 1)[1]
    with sqlite3.connect(path) as con:
        con.executemany(
            "INSERT INTO reaction VALUES (?,?)", [(rid, f"RXN{i:02}") for i in range(20)]
        )
    backend = AgoraLocalBackend(path)
    listed = (
        await backend.fetch(
            "list_reactions",
            [{"microbe.agora.reconstruction_id": MODEL}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"reactions"}),
        )
    )[0]
    assert len(listed.values["reaction.vmh.id"]) == 22
    assert listed.values["microbe.agora.reaction_listing"]["observed_count"] == 22
    assert len(listed.values["microbe.agora.reaction_listing"]["records"]) == 10
    described = await backend.fetch(
        "describe_reaction",
        [
            {"reaction.vmh.id": "23DHMPO"},
            {"reaction.vmh.id": "RXN00"},
            {"reaction.vmh.id": "MISSING"},
        ],
        requested_outputs=frozenset(),
        groups_to_compute=frozenset({"reaction"}),
    )
    assert described[0].values["reaction.vmh.record"]["annotations"]["ec"] == "1.1.1.86"
    assert described[0].values["reaction.vmh.record"]["observed_reconstructions"] == [rid]
    assert described[1].found and described[1].values["reaction.vmh.record"]["annotations"] is None
    assert not described[2].found


async def test_reaction_source_release_and_unprocessed_models_are_errors(tmp_path):
    import shutil

    path = tmp_path / "source.sqlite"
    shutil.copyfile(fixture_reaction_db_path(), path)
    with sqlite3.connect(path) as con:
        con.execute("UPDATE model_coverage SET status='skipped',error='invalid XML'")

    async def lookup():
        return (
            await AgoraLocalBackend(path).fetch(
                "list_reactions",
                [{"microbe.agora.reconstruction_id": MODEL}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset({"reactions"}),
            )
        )[0]

    assert (await lookup()).error
    with sqlite3.connect(path) as con:
        con.execute("UPDATE meta SET value='AGORA2-v2.00' WHERE key='release'")
    assert "release" in (await lookup()).error
