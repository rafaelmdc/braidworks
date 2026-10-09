"""Mappings retain relation evidence; ambiguity cannot become exact identity."""

import sqlite3

from mondo_weaver import setup
from mondo_weaver.backends.local import MondoLocalBackend
from mondo_weaver.fixture import _term


async def _lookup(path, capability, query):
    return (
        await MondoLocalBackend(db_path=path).fetch(
            capability, [query], requested_outputs=frozenset(), groups_to_compute=frozenset()
        )
    )[0]


async def test_equal_name_and_equivalent_xref_candidates_are_order_independent(tmp_path):
    terms = [
        _term(f"MONDO:000000{index}", "shared disease", xrefs=[("MESH", "D1", True)])
        for index in [2, 1]
    ]
    errors = []
    for index, rows in enumerate((terms, list(reversed(terms)))):
        path = tmp_path / f"{index}.sqlite"
        setup.write_db(path, data_version="test", terms=rows)
        name = await _lookup(path, "mondo.lookup_by_name", {"disease.name": "shared disease"})
        xref = await _lookup(path, "mondo.lookup_by_mesh", {"disease.mesh.id": "D1"})
        assert name.error and xref.error and not name.found and not xref.found
        errors.append((name.error, xref.error))
    assert errors[0] == errors[1]


async def test_non_equivalent_relations_and_raw_evidence_survive_parsing(tmp_path):
    predicates = [
        "MONDO:mondoIsBroaderThanSource",
        "MONDO:mondoIsNarrowerThanSource",
        "MONDO:relatedTo",
        "skos:exactMatch",
    ]
    lines = ["data-version: test", "[Term]", "id: MONDO:0000001", "name: disease"]
    lines.extend(
        f'xref: MESH:D{index} {{source="{predicate}"}}'
        for index, predicate in enumerate(predicates)
    )
    version, terms = setup._parse_obo(iter(lines))
    path = tmp_path / "relations.sqlite"
    setup.write_db(path, data_version=version, terms=terms)
    with sqlite3.connect(path) as con:
        assert {row[0] for row in con.execute("SELECT relation FROM xref")} == {
            "mondo_broader",
            "mondo_narrower",
            "related",
            "exact_match",
        }
    for index, predicate in enumerate(predicates):
        record = await _lookup(path, "mondo.lookup_by_mesh", {"disease.mesh.id": f"D{index}"})
        assert record.error and not record.found
        assert predicate in record.error


async def test_unique_equivalence_emits_evidence_without_promoting_other_relations(tmp_path):
    terms = [
        _term("MONDO:0000001", "exact disease", xrefs=[("MESH", "D1", True)]),
        _term("MONDO:0000002", "related disease", xrefs=[("MESH", "D1", False)]),
    ]
    path = tmp_path / "unique.sqlite"
    setup.write_db(path, data_version="test", terms=terms)
    record = await _lookup(path, "mondo.lookup_by_mesh", {"disease.mesh.id": "D1"})
    assert record.found and record.values["disease.mondo.id"] == "MONDO:0000001"
    assert {row["relation"] for row in record.values["disease.ontology.mapping.records"]} == {
        "equivalent",
        "unspecified",
    }


async def test_contradictory_relations_for_same_identity_require_review(tmp_path):
    term = _term("MONDO:0000001", "disease")
    term.xref_evidence = [
        ("MESH", "D1", "equivalent", "source-a"),
        ("MESH", "D1", "related", "source-b"),
    ]
    path = tmp_path / "contradiction.sqlite"
    setup.write_db(path, data_version="test", terms=[term])
    record = await _lookup(path, "mondo.lookup_by_mesh", {"disease.mesh.id": "D1"})
    assert record.error and not record.found
    assert "source-a" in record.error and "source-b" in record.error
