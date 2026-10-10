"""Source grammar and realistic NCBI lineage regressions, independently of scaffolding."""

import pytest
from faprotax_weaver.backends import local
from faprotax_weaver.rules import RuleError, _evaluate, _parse_groups


def test_real_ncbi_binomial_matches_bundled_species_rules():
    groups = local._functional_groups(["Archaea", "Methanosarcina", "Methanosarcina barkeri"])
    assert "methanogenesis" in groups and "acetoclastic_methanogenesis" in groups
    assert not local._functional_groups(["Methanosarcinaxyz", "Methanosarcina barkerixyz"])


@pytest.mark.parametrize(
    "label,expected",
    [
        ("Genus species", True),
        ("gEnUs;species", True),
        ("Genus_species", True),
        ("Genus;others;species", True),
        ("species;Genus", False),
        ("Genusxyz species", False),
        ("Genus speciesxyz", False),
        ("Genus species-like", False),
    ],
)
def test_complete_word_boundaries_and_order(label, expected):
    groups = _parse_groups("function\n*Genus*species*\n")
    assert bool(_evaluate(groups, [label])) is expected


def test_ordered_add_subtract_intersect_and_members_after_subtraction():
    groups = _parse_groups("""a
*Alpha*

b
*Beta*

union
add_group:a
add_group:b

difference
add_group:union
subtract_group:b
*Gamma*

intersection
add_group:union
intersect_group:b
""")
    assert "difference" in _evaluate(groups, ["Alpha"])
    assert "difference" not in _evaluate(groups, ["Alpha", "Beta"])
    assert "difference" in _evaluate(groups, ["Beta", "Gamma"])
    assert "intersection" in _evaluate(groups, ["Beta"])
    assert "intersection" not in _evaluate(groups, ["Alpha"])


def test_bundled_chloroplast_exclusions_and_operator_names():
    groups = local._functional_groups(["Bacteria", "Cyanobacteriia", "chloroplast"])
    assert "oxygenic_photoautotrophy" not in groups
    assert all("group:" not in name for name in local._load_groups())


def test_quotes_group_attributes_and_member_references_are_retained():
    groups = _parse_groups(
        'function\telements:C,H; aerobic:yes\n  "*Genus*species*" # DOI:example\n'
    )
    assert _evaluate(groups, ["Genus species"]) == ["function"]
    assert groups["function"].attributes == (("elements", ("C", "H")), ("aerobic", ("yes",)))
    assert groups["function"].rules[0].reference == "DOI:example"
    with pytest.raises(TypeError):
        groups["new"] = groups["function"]


@pytest.mark.parametrize(
    "text,message",
    [
        ("a\nadd_group:missing\n", "unknown reference"),
        ("a\nadd_group:a\n", "cyclic"),
        ("a\nadd_group:b\n\nb\nadd_group:a\n", "cyclic"),
        ("a\nadd_group:b\n\nb\n*B*\n", "beforehand"),
        ("add_group:a\n", "no group"),
        ("a\n'*unclosed\n", "unterminated"),
        ("a\n*A*\n\na\n*B*", "duplicate"),
    ],
)
def test_invalid_source_rules_are_actionable(text, message):
    with pytest.raises(RuleError, match=message):
        _parse_groups(text)


async def test_invalid_bundled_rules_become_error_records(monkeypatch):
    def invalid():
        raise RuleError("unknown reference")

    monkeypatch.setattr(local, "_load_rules", invalid)
    record = (
        await local.FaprotaxLocalBackend().fetch(
            "describe_ecology",
            [{"ncbi.taxon.lineage": ["Genus"]}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
    )[0]
    assert record.error and not record.found


def test_explanation_tracks_exclusion_then_readdition_and_same_membership():
    groups = _parse_groups(
        "a\n*Alpha* # DOI:alpha\n\nb\nadd_group:a\nsubtract_group:a\n*Beta* # DOI:beta\n"
    )
    trace = {}
    assert _evaluate(groups, ["Alpha", "Beta"], trace=trace) == _evaluate(groups, ["Alpha", "Beta"])
    steps = trace["b"]["operations"]
    assert [(step["before"], step["after"]) for step in steps] == [
        (False, True),
        (True, False),
        (False, True),
    ]
    assert steps[-1]["reference"] == "DOI:beta"
    assert steps[-1]["source_line"] > 0


async def test_requested_evidence_explains_false_membership_and_is_detached():
    backend = local.FaprotaxLocalBackend()
    queries = [{"ncbi.taxon.lineage": [{"name": "Bacteria"}, {"name": "chloroplast"}]}] * 2
    records = await backend.fetch(
        "describe_ecology",
        queries,
        requested_outputs=frozenset({"microbe.ecology.evidence"}),
        groups_to_compute=frozenset({"evidence"}),
    )
    assert records[0].found
    evidence = records[0].values["microbe.ecology.evidence"]
    assert evidence["groups"]["oxygenic_photoautotrophy"]["member"] is False
    evidence["groups"].clear()
    assert records[1].values["microbe.ecology.evidence"]["groups"]
