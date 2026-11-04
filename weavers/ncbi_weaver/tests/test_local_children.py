"""Offline descendants retain the API shape without treating ranks as depths."""

import sqlite3

from braidworks.core import Strand, StrandSet, WeaveStatus
from ncbi_weaver import build_ncbi_weaver, vocab
from ncbi_weaver.backends.local import LocalTaxonomyBackend
from ncbi_weaver.fixture import build_fixture_db


async def test_local_descendants_route_rank_filter_and_detach_duplicates(tmp_path):
    path = build_fixture_db(tmp_path)
    backend = LocalTaxonomyBackend(path)
    records = await backend.list_children(
        [
            {vocab.TAXON_ID: 186803},
            {vocab.TAXON_ID: "186803"},
            {vocab.TAXON_ID: 999999},
            {vocab.TAXON_ID: True},
        ],
        rank="SPECIES",
    )
    assert records[0].values[vocab.TAXON_ID] == [853, 854, 855, 856, 857]
    assert records[0].values[vocab.CHILDREN_COUNT] == 5
    records[0].values[vocab.CHILDREN_RECORDS][0]["name"] = "mutated"
    assert records[1].values[vocab.CHILDREN_RECORDS][0]["name"] != "mutated"
    assert not records[2].found and not records[3].found
    weaver = build_ncbi_weaver(db_path=path)
    cap = weaver.MANIFEST.capability(vocab.LIST_CHILDREN)
    assert cap.backends == ("local",)
    result = await weaver.execute_batch(
        vocab.LIST_CHILDREN,
        [StrandSet.from_strands("family", [Strand(vocab.TAXON_ID, 186803)])],
        requested_outputs=vocab.CHILDREN_OUTPUTS,
        backend="local",
        params={"rank": "genus"},
    )
    assert result[0].status is WeaveStatus.OK
    assert {s.type_id: s.value for s in result[0].strands}[vocab.TAXON_ID] == [239934]


async def test_root_self_edges_and_cycles_terminate_with_uncapped_fan(tmp_path):
    path = build_fixture_db(tmp_path)
    with sqlite3.connect(path) as con:
        con.executemany(
            "INSERT INTO taxa(taxid,parent_taxid,rank) VALUES (?,239934,'species')",
            [(i,) for i in range(900, 1105)],
        )
    backend = LocalTaxonomyBackend(path)
    records = await backend.list_children([{vocab.TAXON_ID: 1}], rank="species")
    assert records[0].values[vocab.CHILDREN_COUNT] == 210
    assert len(records[0].values[vocab.TAXON_ID]) == 210
    assert len(records[0].values[vocab.CHILDREN_RECORDS]) == 200
    with sqlite3.connect(path) as con:
        con.execute("UPDATE taxa SET parent_taxid=853 WHERE taxid=239934")
    cyclic = await LocalTaxonomyBackend(path).list_children([{vocab.TAXON_ID: 239934}], rank="")
    assert 239934 not in cyclic[0].values[vocab.TAXON_ID]
    assert cyclic[0].values[vocab.CHILDREN_COUNT] == 210
