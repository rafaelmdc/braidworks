"""Invalid source snapshots fail before modifying a destination."""

import json
import sqlite3
from copy import deepcopy

import pytest
from braidworks.core import BackendConfigurationError
from disbiome_weaver import fixture, setup


def tables():
    return deepcopy(
        {
            "experiments": fixture._EXPERIMENTS,
            "diseases": fixture._DISEASES,
            "organisms": fixture._ORGANISMS,
            "publications": fixture._PUBLICATIONS,
        }
    )


@pytest.mark.parametrize("case", ["shape", "row", "duplicate", "dangling", "taxid"])
def test_invalid_snapshot_leaves_destination_untouched(tmp_path, case):
    data = tables()
    if case == "shape":
        data["diseases"] = {"error": "unavailable"}
    elif case == "row":
        data["diseases"] = [None]
    elif case == "duplicate":
        data["experiments"].append(deepcopy(data["experiments"][0]))
    elif case == "dangling":
        data["experiments"][0]["publication_id"] = "99999"
    else:
        data["experiments"][0]["organism_ncbi_id"] = -1
    target = tmp_path / "existing.sqlite"
    target.write_bytes(b"previous source")
    with pytest.raises(BackendConfigurationError):
        setup.write_db(target, **data)
    assert target.read_bytes() == b"previous source"


def test_nullable_join_is_explicit_in_coverage(tmp_path):
    data = tables()
    data["experiments"][0]["publication_id"] = "None"
    target = tmp_path / "source.sqlite"
    setup.write_db(target, **data)
    with sqlite3.connect(target) as con:
        metadata = dict(con.execute("SELECT key, value FROM meta"))
        coverage = json.loads(metadata["source_coverage"])
        assert coverage["missing_foreign_identity"]["publication"] == 1
        assert coverage["experiment"]["rows"] == 3
        assert len(coverage["experiment"]["sha256"]) == 64
        assert "not a frozen snapshot" in coverage["snapshot_consistency"]
        record = json.loads(
            con.execute("SELECT full_json FROM association WHERE experiment_id = 1").fetchone()[0]
        )
        assert record["publication"] is None


@pytest.mark.parametrize("table", ["experiments", "diseases", "organisms", "publications"])
def test_duplicate_identity_in_each_source_table_is_rejected(tmp_path, table):
    data = tables()
    data[table].append(deepcopy(data[table][0]))
    with pytest.raises(BackendConfigurationError, match="duplicate identity"):
        setup.write_db(tmp_path / "source.sqlite", **data)
    assert not (tmp_path / "source.sqlite").exists()


def test_integer_foreign_identity_joins_string_primary_identity(tmp_path):
    data = tables()
    data["experiments"][0]["publication_id"] = 1
    target = tmp_path / "source.sqlite"
    setup.write_db(target, **data)
    with sqlite3.connect(target) as con:
        record = json.loads(
            con.execute("SELECT full_json FROM association WHERE experiment_id = 1").fetchone()[0]
        )
        assert record["publication"]["publication_id"] == "1"
