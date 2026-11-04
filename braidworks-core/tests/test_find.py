"""Finding fields by meaning: ``rank_fields`` ranking and ``braidworks.find``."""

from __future__ import annotations

import braidworks as bw
from braidworks.core.capability import Capability, OutputGroup, WeaverManifest
from braidworks.core.catalog import FieldInfo, field_catalog, rank_fields
from braidworks.core.registry import BraidRegistry
from tests.helpers import ScriptedWeaver


def _info(type_id: str, description: str, uses: int = 1) -> FieldInfo:
    return FieldInfo(type_id, description, sources=("src",), inputs=(), consumers=uses)


CATALOG = {
    info.type_id: info
    for info in (
        _info("structure.pdb.ids", "Experimental PDB structures of this protein."),
        _info("structure.pdb.title", "Title of one PDB entry."),
        _info("pdb.id", "One PDB entry identifier.", uses=2),
        _info("ncbi.taxon.id", "NCBI Taxonomy id for one organism.", uses=9),
        _info("gtdb.taxon.id", "GTDB genome-based taxonomy id for one organism.", uses=1),
        _info("go.biological_process", "Gene Ontology biological processes."),
        _info("eggnog.group", "eggNOG orthologous group."),
    )
}


def test_words_in_the_name_and_description_rank_first():
    assert rank_fields("pdb structures", CATALOG)[0].type_id == "structure.pdb.ids"


def test_ties_prefer_the_more_connected_field():
    assert rank_fields("taxon", CATALOG)[0].type_id == "ncbi.taxon.id"


def test_whole_words_not_substrings():
    found = [m.type_id for m in rank_fields("go", CATALOG)]
    assert found == ["go.biological_process"]  # not "eggnog.group"


def test_exact_type_id_wins_and_unknown_words_find_nothing():
    assert rank_fields("pdb.id", CATALOG)[0].type_id == "pdb.id"
    assert rank_fields("zebrafish", CATALOG) == []
    assert rank_fields("  ", CATALOG) == []


def test_partial_word_matches_count():
    assert rank_fields("biolog", CATALOG)[0].type_id == "go.biological_process"


def test_limit():
    assert len(rank_fields("id", CATALOG, limit=2)) == 2


# --- catalog from a registry and the public API ------------------------------

UP = Capability(
    id="resolve_protein",
    consumes=frozenset({"protein.query"}),
    produces=frozenset({"protein.uniprot.accession", "protein.name"}),
    output_groups=(
        OutputGroup(id="g", outputs=frozenset({"protein.uniprot.accession", "protein.name"})),
    ),
    backends=("api",),
)
DOWN = Capability(
    id="list_structures",
    consumes=frozenset({"protein.uniprot.accession"}),
    produces=frozenset({"structure.pdb.ids"}),
    output_groups=(OutputGroup(id="g", outputs=frozenset({"structure.pdb.ids"})),),
    backends=("api",),
)


def _registry() -> BraidRegistry:
    reg = BraidRegistry()
    for weaver_id, cap, descriptions in (
        (
            "uniprot",
            UP,
            {
                "protein.query": "Text you start from: a gene symbol or accession.",
                "protein.name": "Recommended protein name.",
            },
        ),
        ("pdbe", DOWN, {"structure.pdb.ids": "Experimental PDB structures of this protein."}),
    ):
        weaver = ScriptedWeaver(lambda *a: None, capability=cap, weaver_id=weaver_id)
        weaver._manifest = WeaverManifest(
            weaver_id=weaver_id,
            version="1.0.0",
            capabilities=(cap,),
            type_descriptions=descriptions,
        )
        reg.register(weaver)
    return reg


def test_catalog_records_sources_inputs_and_missing_descriptions():
    catalog = field_catalog(_registry())
    pdb = catalog["structure.pdb.ids"]
    assert pdb.sources == ("pdbe",)
    assert pdb.inputs == ("protein.uniprot.accession",)
    assert catalog["protein.query"].consumers == 1
    assert catalog["protein.uniprot.accession"].description == ""  # undescribed but listed


def test_session_find_and_its_display():
    with bw.Session(registry=_registry()) as session:
        found = session.find("pdb structures")
    assert found[0].type_id == "structure.pdb.ids"
    text = repr(found)
    assert "structure.pdb.ids" in text and "Experimental PDB structures" in text
    assert "from protein.uniprot.accession" in text
    assert "<table" in found._repr_html_()
    assert found.to_json()[0]["type_id"] == "structure.pdb.ids"
