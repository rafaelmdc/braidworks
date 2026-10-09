"""Portable source identity and a coherent acyclic ontology are required."""

import hashlib
import sqlite3

import pytest
from mondo_weaver import setup
from mondo_weaver.fixture import _term


def terms():
    return [
        _term("MONDO:0000001", "root", xrefs=[("MESH", "D1", True)]),
        _term("MONDO:0000002", "child", parents=["MONDO:0000001"]),
    ]


def test_missing_version_is_honest_content_identity(tmp_path):
    path = tmp_path / "source.sqlite"
    setup.write_db(path, data_version=None, terms=terms())
    with sqlite3.connect(path) as con:
        meta = dict(con.execute("SELECT key,value FROM meta"))
    assert meta["data_version"] == "unversioned:sha256:" + meta["source_sha256"]
    assert meta["release_known"] == "false" and setup.db_is_valid(path)


@pytest.mark.parametrize("defect", ["cycle", "dangling", "duplicate"])
def test_bad_graph_is_rejected_before_writing(tmp_path, defect):
    rows = terms()
    if defect == "cycle":
        rows[0].parents = [rows[1].mondo_id]
    elif defect == "dangling":
        rows[1].parents = ["MONDO:9999999"]
    else:
        rows.append(rows[0])
    with pytest.raises(ValueError):
        setup.write_db(tmp_path / "source.sqlite", data_version="test-release", terms=rows)
    assert not (tmp_path / "source.sqlite").exists()


@pytest.mark.parametrize("defect", ["cycle", "dangling", "xref", "missing_hash"])
def test_validator_rejects_corrupted_graph_and_provenance(tmp_path, defect):
    path = tmp_path / "source.sqlite"
    setup.write_db(path, data_version="test-release", terms=terms())
    with sqlite3.connect(path) as con:
        if defect == "cycle":
            con.execute("INSERT INTO isa VALUES ('MONDO:0000001','MONDO:0000002')")
        elif defect == "dangling":
            con.execute("INSERT INTO isa VALUES ('MONDO:0000001','MONDO:9999999')")
        elif defect == "xref":
            con.execute("INSERT INTO xref VALUES ('MESH','D2','MONDO:9999999',1)")
        else:
            con.execute("DELETE FROM meta WHERE key='source_sha256'")
    assert not setup.db_is_valid(path)


def test_original_obo_bytes_are_hashed_and_requested_version_checked(tmp_path):
    raw = b"data-version: releases/test\n\n[Term]\nid: MONDO:0000001\nname: root\nxref: MESH:D1\n"

    def download(path, progress):
        path.write_bytes(raw)

    path = tmp_path / "source.sqlite"
    setup._build(path, download=download, expected_version="releases/test")
    with sqlite3.connect(path) as con:
        meta = dict(con.execute("SELECT key,value FROM meta"))
    assert meta["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert meta["source"] == "caller-supplied"
    assert setup.db_is_valid(path)
    with pytest.raises(ValueError, match="mismatch"):
        setup._build(
            tmp_path / "wrong.sqlite", download=download, expected_version="releases/other"
        )


def test_configured_builder_honors_expected_version(monkeypatch, tmp_path):
    from mondo_weaver import factory

    target = tmp_path / "source.sqlite"
    setup.write_db(target, data_version="releases/test", terms=terms())
    calls = []

    def ensure(path, **kwargs):
        calls.append(kwargs)
        return target

    monkeypatch.setattr(factory, "ensure_mondo_db", ensure)
    factory.build_mondo_weaver_configured(db_path=target, expected_version="releases/test")
    assert calls[0]["expected_version"] == "releases/test"
