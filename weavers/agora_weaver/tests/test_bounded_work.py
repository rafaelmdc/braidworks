"""Detached bundled projections and bounded SQL preserve coverage semantics."""

import sqlite3

import pytest
from agora_weaver import dataset


def test_bundled_crosswalk_is_not_mutated_by_a_caller():
    table = dataset.load_crosswalk()
    taxid = next(iter(table))
    expected = dataset.reconstructions_for(taxid)
    table[taxid][0]["reconstruction_id"] = "poisoned"
    table[taxid].clear()
    projection = dataset.reconstructions_for(taxid)
    assert projection == expected
    projection[0]["gcf_id"] = "poisoned"
    assert dataset.reconstructions_for(taxid) == expected


def test_reaction_queries_chunk_deduplicate_and_keep_empty_coverage():
    con = sqlite3.connect(":memory:")
    con.executescript(dataset._SCHEMA)
    ids = [f"m{i:03}" for i in range(251)]
    con.executemany(
        "INSERT INTO model_coverage VALUES (?, 'processed', 0, 'fixture', NULL)",
        ((rid,) for rid in ids),
    )
    con.executemany("INSERT INTO reaction VALUES (?, 'one')", ((rid,) for rid in ids[:-1]))
    statements = []
    con.set_trace_callback(statements.append)
    records = dataset.reactions_for(con, reversed(ids + ids))
    assert [row["reconstruction_id"] for row in records] == ids[:-1]
    assert sum(sql.startswith("SELECT") for sql in statements) == 4
    assert dataset.reactions_for(con, [ids[-1]]) == []
    with pytest.raises(dataset.IncompleteModelCoverage, match="model not acquired"):
        dataset.reactions_for(con, ids + ["missing"])
    con.close()
