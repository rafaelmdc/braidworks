"""Obsolete terms stay describable while resolution indexes remain current-only."""

from mondo_weaver.backends.local import MondoLocalBackend
from mondo_weaver.setup import _parse_obo, db_is_valid, write_db

OBO = """data-version: test-history-release
[Term]
id: MONDO:0005101
name: ulcerative colitis
def: "A disease with \\\"quoted\\\" text." [PMID:1]
xref: MESH:D003093 {source="MONDO:equivalentTo"}
[Term]
id: MONDO:0000002
name: obsolete old condition
is_obsolete: true
replaced_by: MONDO:0005101
xref: MESH:D999999 {source="MONDO:equivalentTo"}
[Term]
id: MONDO:0000003
name: obsolete suggested condition
is_obsolete: true
consider: MONDO:0005101
[Term]
id: MONDO:0000004
name: obsolete no replacement
is_obsolete: true
"""


async def test_direct_current_obsolete_consider_and_unknown(tmp_path):
    version, terms = _parse_obo(iter(OBO.splitlines()))
    assert len(terms) == 4
    path = tmp_path / "history.sqlite"
    write_db(path, data_version=version, terms=terms)
    assert db_is_valid(path)
    backend = MondoLocalBackend(path)
    records = await backend.fetch(
        "describe_disease",
        [
            {"disease.mondo.id": i}
            for i in [
                "MONDO:0005101",
                "MONDO:0000002",
                "MONDO:0000003",
                "MONDO:0000004",
                "MONDO:9999999",
            ]
        ],
        requested_outputs=frozenset(),
        groups_to_compute=frozenset({"history", "definition"}),
    )
    assert records[0].values["disease.ontology.definition"] == 'A disease with "quoted" text.'
    histories = [r.values["disease.ontology.history"] for r in records[:4]]
    assert [h["status"] for h in histories] == ["current", "replaced", "consider", "obsolete"]
    assert histories[2]["consider"] == ["MONDO:0005101"] and histories[2]["replaced_by"] == []
    assert histories[3]["replaced_by"] == []
    assert all(h["source_sha256"] and h["data_version"] == version for h in histories)
    assert not records[4].found
    for capability, query in [
        ("mondo.lookup_by_name", {"disease.name": "obsolete old condition"}),
        ("mondo.lookup_by_mesh", {"disease.mesh.id": "D999999"}),
    ]:
        miss = (
            await backend.fetch(
                capability,
                [query],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset({"identity"}),
            )
        )[0]
        assert not miss.found
