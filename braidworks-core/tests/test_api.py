"""The researcher API: ``braidworks.get``, ``Session`` and ``Result`` (offline network)."""

from __future__ import annotations

import asyncio
import sys

import braidworks as bw
import pytest
from braidworks.core.capability import Capability, OutputGroup, Parameter
from braidworks.core.exceptions import NoPathError
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import Strand
from tests.helpers import ScriptedWeaver

UP_CAP = Capability(
    id="resolve_protein",
    consumes=frozenset({"protein.query"}),
    produces=frozenset({"protein.uniprot.accession", "protein.name"}),
    output_groups=(
        OutputGroup(id="g", outputs=frozenset({"protein.uniprot.accession", "protein.name"})),
    ),
    parameters=(Parameter("organism", description="taxid filter"),),
    backends=("api",),
)
DOWN_CAP = Capability(
    id="list_structures",
    consumes=frozenset({"protein.uniprot.accession"}),
    produces=frozenset({"structure.pdb.ids"}),
    output_groups=(OutputGroup(id="g", outputs=frozenset({"structure.pdb.ids"})),),
    backends=("api",),
)


def _up(ss, backend, requested):
    q = ss.get("protein.query").value
    if q == "MISS":
        return WeaveResult(
            "resolve_protein", "1.0.0", backend, frozenset({"g"}), status=WeaveStatus.NO_MATCH
        )
    return WeaveResult(
        "resolve_protein",
        "1.0.0",
        backend,
        frozenset({"g"}),
        status=WeaveStatus.OK,
        strands=(
            Strand("protein.uniprot.accession", f"ACC_{q}"),
            Strand("protein.name", f"Name of {q}"),
        ),
    )


def _down(ss, backend, requested):
    acc = ss.get("protein.uniprot.accession").value
    return WeaveResult(
        "list_structures",
        "1.0.0",
        backend,
        frozenset({"g"}),
        status=WeaveStatus.OK,
        strands=(Strand("structure.pdb.ids", [f"{acc}-1", f"{acc}-2"]),),
    )


class ClosingWeaver(ScriptedWeaver):
    closed = 0

    async def aclose(self) -> None:
        type(self).closed += 1


def _registry() -> BraidRegistry:
    reg = BraidRegistry()
    reg.register(ClosingWeaver(_up, capability=UP_CAP, weaver_id="uniprot"))
    reg.register(ClosingWeaver(_down, capability=DOWN_CAP, weaver_id="pdbe"))
    return reg


@pytest.fixture
def session():
    with bw.Session(registry=_registry()) as s:
        yield s


def test_get_labels_rows_by_input_and_keeps_order(session):
    result = session.get(
        ["P1", "MISS", "P2"], have="protein.query", want=["protein.name", "structure.pdb.ids"]
    )
    assert [row["input"] for row in result.rows] == ["P1", "MISS", "P2"]
    first = result.rows[0]
    assert first["status"] == "resolved"
    assert first["row"] == 1
    assert first["protein.name"] == "Name of P1"
    assert first["structure.pdb.ids"] == ["ACC_P1-1", "ACC_P1-2"]
    assert first["missing"] == []
    miss = result.rows[1]
    assert miss["status"] == "unresolved"
    assert miss["protein.name"] is None
    assert miss["missing"] == ["protein.name", "structure.pdb.ids"]


def test_single_id_and_single_want_strings(session):
    result = session.get("P1", have="protein.query", want="protein.name")
    assert result.column("protein.name") == {"P1": "Name of P1"}
    assert result["P1"][0]["protein.name"] == "Name of P1"


def test_duplicate_inputs_stay_separate_rows(session):
    result = session.get(["P1", "P1"], have="protein.query", want="protein.name")
    assert [(row["input"], row["row"]) for row in result.rows] == [("P1", 1), ("P1", 2)]


def test_missing_have_is_an_error_with_suggestions(session):
    with pytest.raises(ValueError) as exc:
        session.get(["P1"], want="protein.name")
    message = str(exc.value)
    assert "have=" in message and "protein.query" in message


def test_rows_with_type_names_need_no_have(session):
    result = session.get(
        [{"protein.query": "P1"}, {"protein.uniprot.accession": "ACC_X"}],
        want="structure.pdb.ids",
    )
    assert [row["input"] for row in result.rows] == ["P1", "ACC_X"]
    assert result.rows[1]["structure.pdb.ids"] == ["ACC_X-1", "ACC_X-2"]


def test_column_mapping_input(session):
    result = session.get({"protein.query": ["P1", "P2"]}, want="protein.name")
    assert list(result.column("protein.name")) == ["P1", "P2"]


def test_have_with_typed_rows_is_rejected(session):
    with pytest.raises(ValueError, match="have="):
        session.get([{"protein.query": "P1"}], have="protein.query", want="protein.name")


def test_parameters_are_keywords_and_validated(session):
    result = session.get(["P1"], have="protein.query", want="protein.name", organism="9606")
    assert result.rows[0]["status"] == "resolved"
    assert result.parameters == {"resolve_protein": {"organism": "9606"}}
    with pytest.raises(ValueError, match="organsim"):
        session.get(["P1"], have="protein.query", want="protein.name", organsim="9606")


def test_no_route_explains_in_plain_words(session):
    with pytest.raises(NoPathError) as exc:
        session.get(["P1"], have="protein.query", want="protein.nam")
    assert "`protein.name`" in str(exc.value)


def test_summary_and_missing(session):
    result = session.get(["P1", "MISS"], have="protein.query", want="protein.name")
    assert result.summary() == "2 inputs · 1 resolved · 1 unresolved · 0 need review · 0 errors"
    assert [row["input"] for row in result.missing] == ["MISS"]
    assert "1 resolved" in repr(result)
    assert "<table" in result._repr_html_()


def test_to_csv_flattens_lists(session, tmp_path):
    result = session.get(["P1"], have="protein.query", want="structure.pdb.ids")
    text = result.to_csv()
    assert text.splitlines()[0] == "input,row,status,structure.pdb.ids,missing"
    assert "ACC_P1-1; ACC_P1-2" in text
    out = tmp_path / "rows.tsv"
    result.to_csv(out, sep="\t")
    assert out.read_text().startswith("input\trow\tstatus")


def test_to_pandas(session):
    pd = pytest.importorskip("pandas")
    result = session.get(["P1"], have="protein.query", want="structure.pdb.ids")
    frame = result.to_pandas()
    assert isinstance(frame, pd.DataFrame)
    assert list(frame.columns) == ["input", "row", "status", "structure.pdb.ids", "missing"]
    assert len(result.to_pandas(explode="structure.pdb.ids")) == 2


def test_to_pandas_without_pandas_says_how_to_install(session, monkeypatch):
    monkeypatch.setitem(sys.modules, "pandas", None)
    result = session.get(["P1"], have="protein.query", want="protein.name")
    with pytest.raises(ImportError, match=r"braidworks-core\[pandas\]"):
        result.to_pandas()


def test_sync_get_works_inside_a_running_loop(session):
    async def notebook_cell():
        return session.get(["P1"], have="protein.query", want="protein.name")

    result = asyncio.run(notebook_cell())
    assert result.rows[0]["protein.name"] == "Name of P1"


def test_async_get(session):
    result = asyncio.run(session.async_get(["P1"], have="protein.query", want="protein.name"))
    assert result.rows[0]["protein.name"] == "Name of P1"


def test_session_reuses_weavers_and_closes_them_once():
    ClosingWeaver.closed = 0
    with bw.Session(registry=_registry()) as s:
        s.get(["P1"], have="protein.query", want="protein.name")
        s.get(["P2"], have="protein.query", want="protein.name")
        assert ClosingWeaver.closed == 0
    assert ClosingWeaver.closed == 2


def test_path_and_sources(session):
    route = session.path("protein.query", "structure.pdb.ids")
    assert [step.capability_id for step in route.steps] == ["resolve_protein", "list_structures"]
    assert {record["source"] for record in session.sources()} == {"pdbe", "uniprot"}


def test_references_and_route_are_kept(session):
    result = session.get(["P1"], have="protein.query", want="structure.pdb.ids")
    assert [step.capability_id for braid in result.route for step in braid.steps] == [
        "resolve_protein",
        "list_structures",
    ]
    assert isinstance(result.cite(), str)
    assert result.raw.resolved


def test_module_level_get_uses_discovery(monkeypatch):
    from braidworks import _session

    monkeypatch.setattr(_session, "build_registry_from_entry_points", lambda only=None: _registry())
    result = bw.get(["P1"], have="protein.query", want="protein.name", sources="uniprot")
    assert result.rows[0]["protein.name"] == "Name of P1"


def test_weaver_author_namespace():
    from braidworks import weaver

    for name in ("BackendBase", "BackendDispatchWeaver", "LookupRecord", "map_lookup"):
        assert hasattr(weaver, name)


def test_route_prints_like_the_cli(session):
    text = str(session.path("protein.query", "structure.pdb.ids"))
    assert text.splitlines()[0] == "protein.query  →  structure.pdb.ids   (2 steps)"
    assert "1. uniprot.resolve_protein [api]" in text
