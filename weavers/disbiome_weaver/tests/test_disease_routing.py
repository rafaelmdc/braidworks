"""Provider identity and code multiplicity survive reverse traversal."""

from copy import deepcopy

from disbiome_weaver.backends.local import DisbiomeLocalBackend
from disbiome_weaver.fixture import _DISEASES, _EXPERIMENTS, _ORGANISMS, _PUBLICATIONS
from disbiome_weaver.setup import write_db


async def test_code_multiplicity_exact_identity_and_generic_taxon_fan(tmp_path):
    experiments = deepcopy(_EXPERIMENTS)
    diseases = deepcopy(_DISEASES)
    diseases.append({**diseases[1], "disease_id": "3", "name": "Distinct provider disease"})
    experiments.append(
        {
            **experiments[0],
            "experiment_id": "4",
            "disease_id": "3",
            "meddra_id": "10011401",
            "disease_name": "Distinct provider disease",
        }
    )
    path = tmp_path / "reverse.sqlite"
    write_db(
        path,
        experiments=experiments,
        diseases=diseases,
        organisms=_ORGANISMS,
        publications=_PUBLICATIONS,
    )
    backend = DisbiomeLocalBackend(path)

    async def fetch(cap, query, groups=(), params=None):
        return (
            await backend.fetch(
                cap,
                [query],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset(groups),
                params=params,
            )
        )[0]

    reverse = await fetch("disbiome.list_taxa", {"disease.meddra.id": "10011401"})
    assert reverse.values["ncbi.taxon.id"] == [1350, 1591]
    evidence = reverse.values["microbe.disease.taxa"]
    assert evidence["matched_disease_ids"] == [2, 3]
    assert evidence["experiment_count"] == 3
    assert evidence["records"][0]["publication"]["title"]
    exact = await fetch("disbiome.list_taxa", {"disease.disbiome.id": 2})
    assert exact.values["ncbi.taxon.id"] == [1350]
    filtered = await fetch(
        "disbiome.list_taxa", {"disease.disbiome.id": 2}, params={"outcome": "Reduced"}
    )
    assert filtered.values["microbe.disease.taxa"]["experiment_count"] == 1
    assert not (
        await fetch(
            "disbiome.list_taxa", {"disease.disbiome.id": 999, "disease.meddra.id": "10011401"}
        )
    ).found
    identity = await fetch("disbiome.list_diseases", {"ncbi.taxon.id": 1350}, {"identity"})
    assert identity.values["disease.disbiome.id"] == [2]
    assert identity.values["disease.meddra.id"] == ["10011401"]
    disease = await fetch("disbiome.describe_disease", {"disease.disbiome.id": 2})
    assert (
        disease.values["disease.disbiome.record"]["source_records"][0]["name"] == "Crohn's disease"
    )
