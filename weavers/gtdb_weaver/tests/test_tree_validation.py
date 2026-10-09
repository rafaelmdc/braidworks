"""Malformed geometry and ambiguous leaf identities never become usable artifacts."""

import hashlib

import pytest
from gtdb_weaver import setup
from gtdb_weaver.tree import NewickError, load_rootpath_index, load_rootpaths, parse_newick


@pytest.mark.parametrize(
    "text",
    [
        "",
        " ;",
        "();",
        "(,A);",
        "(A,A);",
        "A;B;",
        "A:NaN;",
        "A:inf;",
        "A:-1;",
        "((A:1e308):1e308);",
        "(A,B",
        "'unterminated",
    ],
)
def test_invalid_tree_is_rejected(text):
    with pytest.raises(NewickError):
        parse_newick(text)


def test_valid_labels_zero_missing_and_scientific_lengths_are_preserved():
    index = load_rootpath_index(["('A''quoted':0,B:1e-3,C); \n"])
    assert index.path_for("A'quoted")[-1][1] == 0
    assert index.path_for("B")[-1][1] == 0.001
    assert index.path_for("C")[-1][1] == 0


@pytest.mark.parametrize("loader", [load_rootpaths, load_rootpath_index])
def test_duplicate_forest_labels_are_rejected(loader):
    with pytest.raises(NewickError, match="duplicate leaf"):
        loader(["(A,B);", "(A,C);"])


def test_checksum_valid_malformed_download_preserves_existing_tree(tmp_path, monkeypatch):
    target = tmp_path / "bac.tree"
    target.write_text("(Old:1,Other:1);")
    original = target.read_bytes()
    malformed = b"(A:NaN,B:1);"
    resource = {"url": "https://fixture/tree", "md5": hashlib.md5(malformed).hexdigest()}
    bundle = {"release": "R232", "resources": {"bac120_tree": resource, "ar53_tree": resource}}
    monkeypatch.setattr(setup, "default_tree_paths", lambda _: [target, tmp_path / "ar.tree"])
    monkeypatch.setattr(setup, "_MIN_FREE_BYTES", 0)
    monkeypatch.setattr(setup, "_download", lambda url, dest, **kw: dest.write_bytes(malformed))
    with pytest.raises(NewickError, match="branch length"):
        setup.ensure_gtdb_trees(auto=True, refresh=True, bundle=bundle)
    assert target.read_bytes() == original
