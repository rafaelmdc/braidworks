"""Release coherence and typed mapping evidence are independent of identity lookup."""

import hashlib

import pytest
from mondo_weaver.backends.local import MondoLocalBackend
from mondo_weaver.fixture import _term
from mondo_weaver.setup import db_is_valid, parse_sssom, write_db

SSSOM = """# mapping_set_id: http://purl.obolibrary.org/obo/mondo/mappings/mondo.sssom.tsv
subject_id\tsubject_label\tpredicate_id\tobject_id\tobject_label\tmapping_justification
MONDO:0000001\tdisease\tskos:exactMatch\tDOID:4\tdisease\tsemapv:UnspecifiedMatching
MONDO:0000001\tdisease\tskos:broadMatch\tmesh:D004194\t\tsemapv:UnspecifiedMatching
"""


def build(path, release="2026-10-06"):
    rows, metadata = parse_sssom(iter(SSSOM.splitlines(True)))
    write_db(
        path,
        data_version="releases/2026-10-06",
        terms=[_term("MONDO:0000001", "disease", xrefs=[("MESH", "D1", True)])],
        mappings=rows,
        mapping_source={
            "release": release,
            "sha256": hashlib.sha256(SSSOM.encode()).hexdigest(),
            "metadata": metadata,
        },
    )


async def test_typed_mappings_keep_direction_provenance_and_detach_duplicates(tmp_path):
    path = tmp_path / "typed.sqlite"
    build(path)
    assert db_is_valid(path)
    backend = MondoLocalBackend(path)
    records = await backend.fetch(
        "describe_disease",
        [{"disease.mondo.id": "MONDO:0000001"}] * 2,
        requested_outputs=frozenset(),
        groups_to_compute=frozenset({"mappings"}),
    )
    mapping = records[0].values["disease.ontology.external_mappings"]
    assert {row["predicate_id"] for row in mapping["records"]} == {
        "skos:exactMatch",
        "skos:broadMatch",
    }
    assert mapping["source"]["sha256"] and mapping["data_version"] == "releases/2026-10-06"
    mapping["records"].clear()
    assert len(records[1].values["disease.ontology.external_mappings"]["records"]) == 2


def test_mismatched_release_rejected_before_publish(tmp_path):
    path = tmp_path / "wrong.sqlite"
    with pytest.raises(ValueError, match="releases must match"):
        build(path, "2026-09-01")
    assert not path.exists()


@pytest.mark.parametrize(
    "text",
    [
        SSSOM.replace("predicate_id", "subject_id"),
        SSSOM.replace("\tskos:broadMatch\t", "\t\t"),
        SSSOM + "MONDO:1\tskos:exactMatch\n",
    ],
)
def test_malformed_rows_are_rejected(text):
    with pytest.raises(ValueError):
        parse_sssom(iter(text.splitlines(True)))
