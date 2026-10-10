"""Exact identity never becomes an inferred species-level observation."""

from copy import deepcopy

from disbiome_weaver.backends.local import DisbiomeLocalBackend
from disbiome_weaver.fixture import _DISEASES, _EXPERIMENTS, _ORGANISMS, _PUBLICATIONS
from disbiome_weaver.setup import write_db


async def test_rank_is_source_evidence_and_coverage_respects_filters(tmp_path):
    organisms = deepcopy(_ORGANISMS)
    organisms[1]["rank"] = "genus"
    path = tmp_path / "ranks.sqlite"
    write_db(
        path,
        experiments=_EXPERIMENTS,
        diseases=_DISEASES,
        organisms=organisms,
        publications=_PUBLICATIONS,
    )
    backend = DisbiomeLocalBackend(path)
    records = await backend.fetch(
        "disbiome.list_diseases",
        [
            {"ncbi.taxon.id": 1350},
            {"ncbi.taxon.species_id": 1350},
            {"ncbi.taxon.id": 1591},
            {"ncbi.taxon.id": 999999, "ncbi.taxon.species_id": 1350},
        ],
        requested_outputs=frozenset(),
        groups_to_compute=frozenset({"coverage"}),
        params={"outcome": "Reduced"},
    )
    coverage = records[0].values["microbe.disease.coverage"]
    assert coverage == records[1].values["microbe.disease.coverage"]
    assert coverage["organisms"][0]["rank"] == "genus"
    assert coverage["matched_taxid"] == 1350
    assert coverage["rank_available"]
    assert coverage["experiment_count"] == 1
    assert coverage["lookup_policy"] == "exact"
    assert not coverage["ancestor_rollup"]
    assert not coverage["propagated_to_descendants"]
    assert not records[2].found and not records[3].found
    coverage["organisms"][0]["rank"] = "changed"
    assert records[1].values["microbe.disease.coverage"]["organisms"][0]["rank"] == "genus"
    unknown = (
        await backend.fetch(
            "disbiome.list_diseases",
            [{"ncbi.taxon.species_id": 1591}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"coverage", "summary"}),
        )
    )[0].values
    assert unknown["microbe.disease.count"] == 1
    assert unknown["microbe.disease.coverage"]["organisms"][0]["rank"] is None
    assert not unknown["microbe.disease.coverage"]["rank_available"]
