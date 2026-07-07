"""Unit tests for the reference-tree geometry (Newick → root paths → patristic)."""

from __future__ import annotations

import json

import pytest

from gtdb_weaver.tree import build_rootpaths, cophenetic, parse_newick

# R
# ├─ X:0.5 ── A:1, B:2
# └─ Y:1.5 ── C:3, D:4
_TREE = "((A:1,B:2)X:0.5,(C:3,D:4)Y:1.5)R;"


def _paths():
    return build_rootpaths(parse_newick(_TREE))


def test_leaves_recovered():
    assert set(_paths()) == {"A", "B", "C", "D"}


def test_leaf_depths_are_cumulative():
    paths = _paths()
    assert paths["A"][-1][1] == pytest.approx(1.5)  # R(0) + X(0.5) + A(1)
    assert paths["D"][-1][1] == pytest.approx(5.5)  # R(0) + Y(1.5) + D(4)


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("A", "B", 3.0),  # via X: 1 + 2
        ("C", "D", 7.0),  # via Y: 3 + 4
        ("A", "C", 6.0),  # via R: (1+0.5) + (3+1.5)
        ("B", "D", 8.0),  # via R: (2+0.5) + (4+1.5)
        ("A", "A", 0.0),  # a leaf to itself
    ],
)
def test_patristic_distance(a, b, expected):
    paths = _paths()
    assert cophenetic(paths[a], paths[b]) == pytest.approx(expected)


def test_cophenetic_is_symmetric():
    paths = _paths()
    assert cophenetic(paths["A"], paths["D"]) == pytest.approx(cophenetic(paths["D"], paths["A"]))


def test_survives_json_roundtrip():
    """Strand values round-trip through JSON, turning (id, depth) tuples into lists."""
    paths = _paths()
    a = json.loads(json.dumps(paths["A"]))
    c = json.loads(json.dumps(paths["C"]))
    assert cophenetic(a, c) == pytest.approx(6.0)


def test_quoted_and_internal_labels():
    """GTDB internal labels are support/taxon strings, sometimes single-quoted."""
    tree = "((A:1,B:2)'100.0:g__Foo':0.5,C:3)root;"
    paths = build_rootpaths(parse_newick(tree))
    assert set(paths) == {"A", "B", "C"}
    assert cophenetic(paths["A"], paths["B"]) == pytest.approx(3.0)


def test_whitespace_and_no_trailing_semicolon():
    paths = build_rootpaths(parse_newick("(A:1.0,\n B:2.0)R"))
    assert cophenetic(paths["A"], paths["B"]) == pytest.approx(3.0)
