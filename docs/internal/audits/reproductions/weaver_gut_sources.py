import asyncio
import tempfile
from pathlib import Path

from agora_weaver.backends.local import AgoraLocalBackend
from agora_weaver.weaver import AgoraWeaver
from braidworks.core import Strand, StrandSet
from disbiome_weaver.factory import build_disbiome_weaver_fixture
from gmrepo_weaver.backends.local import GmrepoLocalBackend
from gmrepo_weaver.setup import _fetch_run_ids, _fetch_tables, _num, write_db


def post(endpoint, body):
    if endpoint == "get_all_gut_microbes":
        return {
            "all_genus": [
                {"ncbi_taxon_id": 816, "name": "Bacteroides"},
                {"ncbi_taxon_id": 1350, "name": "Enterococcus"},
            ]
        }
    if endpoint == "get_all_phenotypes":
        return {"phenotypes": [{"disease": "D1", "term": "Case"}]}
    if body.get("ncbi_taxon_id") == 1350:
        raise OSError("fixture failed request")
    return {
        "phenotypes_associated_with_taxon": [
            {"disease": "D1", "term": "Case", "samples": 1, "valid_runs": 2}
        ]
    }


async def main():
    overview, associations, phenotypes = _fetch_tables(post)
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "gm.sqlite"
        write_db(db, overview=overview, associations=associations, phenotypes=phenotypes)
        record = (
            await GmrepoLocalBackend(db).fetch(
                "gmrepo.list_abundances",
                [{"ncbi.taxon.id": 1350}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset(),
            )
        )[0]
        print("Failed taxon becomes", record.found, record.error, record.values)
    with tempfile.TemporaryDirectory() as directory:
        agora = AgoraWeaver(
            {
                "local": AgoraLocalBackend(
                    Path(directory) / "absent.sqlite", sbml_cache_dir=directory
                )
            }
        )
        for output in ("microbe.metabolism.reactions", "microbe.metabolism.sbml"):
            result = (
                await agora.execute_batch(
                    "describe_metabolic_reconstruction",
                    [StrandSet.from_strands("e", [Strand("ncbi.taxon.id", "592010")])],
                    requested_outputs=frozenset({output}),
                    backend="local",
                )
            )[0]
            print(
                "AGORA requested absent",
                output,
                result.status,
                result.strands,
                result.computed_groups,
            )
    w = build_disbiome_weaver_fixture()
    for key in ["ncbi.taxon.id", "ncbi.taxon.species_id"]:
        result = (
            await w.execute_batch(
                "disbiome.list_diseases",
                [StrandSet.from_strands("e", [Strand(key, 1350)])],
                requested_outputs=frozenset({"microbe.disease.count"}),
                backend="local",
            )
        )[0]
        print("Genus1350 supplied as", key, result.status)
    print("Numeric nonfinite", _num("nan"))
    print(
        "Duplicate run list",
        _fetch_run_ids(lambda e, b: [{"run_id": "same"}, {"run_id": "same"}], "D1", 2),
    )


asyncio.run(main())
