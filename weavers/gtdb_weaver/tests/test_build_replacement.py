"""Public crosswalk builders publish complete validated replacements."""

import sqlite3
from unittest.mock import patch

import pytest
from gtdb_weaver import setup, taxonomy


def rows(taxid):
    return [(taxid, f"d__Bacteria;s__Species {taxid}", True, f"GCF_{taxid}")]


def test_rebuild_removes_old_taxa_species_and_metadata(tmp_path):
    target = tmp_path / "crosswalk.sqlite"
    taxonomy.build_crosswalk_db(rows(1), target, release="R1")
    taxonomy.build_crosswalk_db(rows(2), target, release="R2")
    with taxonomy.open_ro(target) as con:
        assert con.execute("SELECT ncbi_taxid FROM taxon").fetchall() == [(2,)]
        assert con.execute("SELECT name FROM species").fetchall() == [("species 2",)]
    assert taxonomy.db_release(target) == "R2"
    assert setup.db_is_valid(target)


@pytest.mark.parametrize("failure", ["iterator", "empty", "release", "publication"])
@pytest.mark.parametrize("existing", [True, False])
def test_failed_replacement_preserves_target(tmp_path, failure, existing):
    target = tmp_path / "crosswalk.sqlite"
    if existing:
        taxonomy.build_crosswalk_db(rows(1), target, release="R1")
    before = target.read_bytes() if existing else None

    def failing_rows():
        yield from rows(2)
        raise ValueError("broken input")

    if failure == "publication":
        with (
            patch("braidworks.core.localdb.os.replace", side_effect=OSError("publish")),
            pytest.raises(OSError),
        ):
            taxonomy.build_crosswalk_db(rows(2), target, release="R2")
    else:
        with pytest.raises(ValueError):
            taxonomy.build_crosswalk_db(
                failing_rows()
                if failure == "iterator"
                else ([] if failure == "empty" else rows(2)),
                target,
                release="" if failure == "release" else "R2",
            )
    assert (target.read_bytes() if target.exists() else None) == before
    assert all(p.name in {target.name, target.name + ".lock"} for p in tmp_path.iterdir())


def test_incomplete_schema_is_not_reusable(tmp_path):
    target = tmp_path / "crosswalk.sqlite"
    with sqlite3.connect(target) as con:
        con.execute("CREATE TABLE taxon (ncbi_taxid INTEGER)")
        con.execute("INSERT INTO taxon VALUES (1)")
    assert not setup.db_is_valid(target)
