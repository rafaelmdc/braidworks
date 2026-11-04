"""Compact evidence remains traceable; filters apply consistently to every slice."""

import sqlite3

from disbiome_weaver.backends.local import DisbiomeLocalBackend
from disbiome_weaver.fixture import _DISEASES, _EXPERIMENTS, _ORGANISMS, _PUBLICATIONS
from disbiome_weaver.setup import db_is_valid, write_db


async def test_compact_identity_matches_full_and_filters_all_groups(tmp_path):
    path = tmp_path / "evidence.sqlite"
    write_db(
        path,
        experiments=_EXPERIMENTS,
        diseases=_DISEASES,
        organisms=_ORGANISMS,
        publications=_PUBLICATIONS,
    )
    backend = DisbiomeLocalBackend(path)

    async def lookup(groups, params=None):
        return (
            await backend.fetch(
                "disbiome.list_diseases",
                [{"ncbi.taxon.id": "1350"}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset(groups),
                params=params,
            )
        )[0]

    all_groups = await lookup({"summary", "associations", "full"})
    assert all_groups.values["microbe.disease.count"] == 2
    compact = await lookup({"associations"})
    assert (
        compact.values["microbe.disease.associations"]
        == all_groups.values["microbe.disease.associations"]
    )
    for evidence, raw in zip(
        compact.values["microbe.disease.associations"], all_groups.values["microbe.disease.records"]
    ):
        assert str(evidence["experiment_id"]) == str(raw["experiment_id"])
        for key in ("publication_id", "organism_id", "disease_id"):
            assert str(evidence[key]) == str(raw[key])
    filters = {"outcome": "Reduced", "sample": "Faeces", "method": "qPCR"}
    filtered = await lookup({"summary", "associations", "full"}, filters)
    assert filtered.values["microbe.disease.count"] == 1
    assert str(filtered.values["microbe.disease.associations"][0]["experiment_id"]) == "3"
    assert (await lookup({"summary"}, filters)).values["microbe.disease.count"] == 1
    assert (await lookup({"associations"}, filters)).values[
        "microbe.disease.associations"
    ] == filtered.values["microbe.disease.associations"]
    assert not (await lookup({"full"}, {"sample": "Faeces' OR 1=1 --"})).found
    assert not (await lookup(set(), {"method": "unknown"})).found
    with sqlite3.connect(path) as con:
        con.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
    assert not db_is_valid(path)


async def test_missing_publication_and_context_remain_unknown(tmp_path):
    experiment = {**_EXPERIMENTS[0], "publication_id": None, "sample_name": None}
    path = tmp_path / "missing.sqlite"
    write_db(
        path,
        experiments=[experiment],
        diseases=_DISEASES,
        organisms=_ORGANISMS,
        publications=_PUBLICATIONS,
    )
    backend = DisbiomeLocalBackend(path)
    query = [{"ncbi.taxon.id": "1591"}]
    record = (
        await backend.fetch(
            "disbiome.list_diseases",
            query,
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"associations"}),
        )
    )[0]
    assert record.values["microbe.disease.associations"][0]["publication_id"] is None
    result = await backend.fetch(
        "disbiome.list_diseases",
        query,
        requested_outputs=frozenset(),
        groups_to_compute=frozenset({"summary"}),
        params={"sample": "Faeces"},
    )
    assert not result[0].found
