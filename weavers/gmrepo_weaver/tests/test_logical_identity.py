"""Repeated acquisition rows cannot inflate stored counts or change source identity."""

import sqlite3

import pytest
from gmrepo_weaver import fixture
from gmrepo_weaver.setup import db_is_valid, write_db


def _write(path, *, duplicated=False, reversed_rows=False):
    def rows(values):
        values = list(reversed(values)) if reversed_rows else list(values)
        return values + values if duplicated else values

    write_db(
        path,
        overview=rows(fixture._OVERVIEW),
        associations=rows(fixture._ASSOCIATIONS),
        phenotypes=rows(fixture._PHENOTYPES),
        sample_profiles=rows(fixture._SAMPLE_PROFILES),
    )


def test_duplicate_rows_and_permutations_have_same_logical_content(tmp_path):
    hashes = []
    for index, (duplicated, reversed_rows) in enumerate(
        [(False, False), (True, False), (True, True)]
    ):
        path = tmp_path / f"{index}.sqlite"
        _write(path, duplicated=duplicated, reversed_rows=reversed_rows)
        assert db_is_valid(path)
        with sqlite3.connect(path) as connection:
            hashes.append(
                connection.execute("SELECT value FROM meta WHERE key='content_sha256'").fetchone()[
                    0
                ]
            )
            assert connection.execute("SELECT COUNT(*) FROM association").fetchone()[0] == len(
                fixture._ASSOCIATIONS
            )
            assert connection.execute("SELECT COUNT(*) FROM sample_profile").fetchone()[0] == len(
                fixture._SAMPLE_PROFILES
            )
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO sample_profile SELECT * FROM sample_profile LIMIT 1"
                )
    assert len(set(hashes)) == 1


def test_conflicting_identity_rejected_before_database_created(tmp_path):
    path = tmp_path / "conflict.sqlite"
    row = fixture._ASSOCIATIONS[0]
    with pytest.raises(ValueError, match="Conflicting GMrepo"):
        write_db(path, overview=[], phenotypes=[], associations=[row, {**row, "samples": 999}])
    assert not path.exists()


def test_legacy_schema_requires_rebuild(tmp_path):
    path = tmp_path / "legacy.sqlite"
    _write(path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
    assert not db_is_valid(path)
