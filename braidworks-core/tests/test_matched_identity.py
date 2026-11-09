"""Rows show what an input matched: the identity a source always returns."""

from __future__ import annotations

import braidworks as bw
from braidworks.core import cli
from braidworks.core.capability import Capability, OutputGroup
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import Strand
from tests.test_api import DOWN_CAP, ClosingWeaver, _down

IDENTITY = frozenset({"protein.uniprot.accession", "protein.organism"})
RESOLVE = Capability(
    id="resolve_protein",
    consumes=frozenset({"protein.query"}),
    produces=IDENTITY | {"protein.name"},
    output_groups=(
        OutputGroup(id="identity", outputs=IDENTITY),
        OutputGroup(id="names", outputs=frozenset({"protein.name"})),
    ),
    backends=("api",),
    always_computed_groups=frozenset({"identity"}),
)


def _resolve(ss, backend, requested):
    query = ss.get("protein.query").value
    if query == "MISS":
        return WeaveResult("resolve_protein", "1", backend, frozenset(), WeaveStatus.NO_MATCH)
    return WeaveResult(
        "resolve_protein",
        "1",
        backend,
        frozenset({"identity", "names"}),
        WeaveStatus.OK,
        strands=(
            Strand("protein.uniprot.accession", f"ACC_{query}"),
            Strand("protein.organism", "Rattus norvegicus"),
            Strand("protein.name", f"{query} homolog"),
        ),
    )


def _registry():
    registry = BraidRegistry()
    registry.register(ClosingWeaver(_resolve, capability=RESOLVE, weaver_id="uniprot"))
    registry.register(ClosingWeaver(_down, capability=DOWN_CAP, weaver_id="pdbe"))
    return registry


def _get(ids, want):
    with bw.Session(registry=_registry()) as s:
        return s.get(ids, have="protein.query", want=want)


def test_rows_show_the_identity_the_input_matched():
    result = _get(["BRCA1", "MISS"], ["protein.name"])
    hit, miss = result.rows
    # identifiers other sources join on come first
    assert list(hit["matched"].items()) == [
        ("protein.uniprot.accession", "ACC_BRCA1"),
        ("protein.organism", "Rattus norvegicus"),
    ]
    assert "matched" not in miss  # an unresolved row is explained by its status
    header, first, _ = result.to_csv().splitlines()
    assert header == "input,row,status,matched,protein.name,missing"
    assert first.startswith(
        "BRCA1,1,resolved,protein.uniprot.accession=ACC_BRCA1; protein.organism=Rattus norvegicus,"
    )
    assert result.to_json()["rows"][0]["matched"] == hit["matched"]


def test_requested_identity_fields_are_not_repeated():
    result = _get(["BRCA1"], ["protein.name", "protein.uniprot.accession", "protein.organism"])
    assert "matched" not in result.rows[0]
    assert "matched" not in result.columns


def test_steps_that_do_not_start_from_the_input_add_nothing():
    with bw.Session(registry=_registry()) as s:
        result = s.get(["ACC_X"], have="protein.uniprot.accession", want="structure.pdb.ids")
    assert "matched" not in result.rows[0]


def test_human_output_prints_the_match(monkeypatch, capsys):
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: _registry())
    assert cli.main(["get", "BRCA1", "--have", "protein.query", "--want", "protein.name"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[1] == (
        "  matched: protein.uniprot.accession=ACC_BRCA1; protein.organism=Rattus norvegicus"
    )
