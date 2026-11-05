"""The researcher API: ``braidworks.get``, ``Session`` and ``Result`` (offline network)."""

from __future__ import annotations

import asyncio
import sys

import braidworks as bw
import pytest
from braidworks.core.capability import Capability, OutputGroup, Parameter
from braidworks.core.exceptions import NoPathError
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import CandidateResult, WeaveResult, WeaveStatus
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
    produces=frozenset({"structure.pdb.ids", "structure.pdb.count"}),
    output_groups=(
        OutputGroup(id="g", outputs=frozenset({"structure.pdb.ids", "structure.pdb.count"})),
    ),
    backends=("api",),
    totals={"structure.pdb.ids": "structure.pdb.count"},
)


def _up(ss, backend, requested):
    q = ss.get("protein.query").value
    if q == "MISS":
        return WeaveResult(
            "resolve_protein", "1.0.0", backend, frozenset({"g"}), status=WeaveStatus.NO_MATCH
        )
    if q == "AMB":  # two plausible proteins: needs a human choice
        return WeaveResult(
            "resolve_protein",
            "1.0.0",
            backend,
            frozenset({"g"}),
            status=WeaveStatus.AMBIGUOUS,
            candidates=tuple(
                CandidateResult(
                    (
                        Strand("protein.uniprot.accession", f"ACC_{suffix}"),
                        Strand("protein.name", f"Candidate {suffix}"),
                    ),
                    confidence,
                )
                for suffix, confidence in (("A", 0.6), ("B", 0.4))
            ),
        )
    if q == "FLAG":  # resolved, but the source asks for confirmation
        return WeaveResult(
            "resolve_protein",
            "1.0.0",
            backend,
            frozenset({"g"}),
            status=WeaveStatus.OK,
            strands=(
                Strand("protein.uniprot.accession", "ACC_FLAG"),
                Strand("protein.name", "Flagged name"),
            ),
            requires_review=True,
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
        strands=(
            # the source returned 2 of its 5 structures
            Strand("structure.pdb.ids", [f"{acc}-1", f"{acc}-2"], total=5, complete=False),
            Strand("structure.pdb.count", 5),
        ),
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
    assert text.splitlines()[0] == (
        "input,row,status,structure.pdb.ids,structure.pdb.ids.total,missing"
    )
    assert "ACC_P1-1; ACC_P1-2" in text
    out = tmp_path / "rows.tsv"
    result.to_csv(out, sep="\t")
    assert out.read_text().startswith("input\trow\tstatus")


def test_to_pandas(session):
    pd = pytest.importorskip("pandas")
    result = session.get(["P1"], have="protein.query", want="structure.pdb.ids")
    frame = result.to_pandas()
    assert isinstance(frame, pd.DataFrame)
    assert list(frame.columns) == [
        "input",
        "row",
        "status",
        "structure.pdb.ids",
        "structure.pdb.ids.total",
        "missing",
    ]
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


# --- resolving ambiguous matches from Python ---------------------------------


def test_review_lists_paused_rows_with_numbered_candidates(session):
    result = session.get(["P1", "AMB"], have="protein.query", want="structure.pdb.ids")
    assert [row["status"] for row in result.rows] == ["resolved", "review"]
    (item,) = result.review
    assert item.input == "AMB" and item.ambiguous
    assert [c["index"] for c in item.candidates] == [0, 1]
    assert item.candidates[1]["values"]["protein.name"] == "Candidate B"
    assert "AMB" in repr(item) and "Candidate B" in repr(item)


def test_choose_then_resume_continues_downstream(session):
    result = session.get(["P1", "AMB"], have="protein.query", want="structure.pdb.ids")
    result.review[0].choose(1)
    resumed = result.resume()
    assert [row["status"] for row in resumed.rows] == ["resolved", "resolved"]
    assert resumed["AMB"][0]["structure.pdb.ids"] == ["ACC_B-1", "ACC_B-2"]
    assert resumed["P1"][0]["structure.pdb.ids"] == ["ACC_P1-1", "ACC_P1-2"]  # kept
    assert resumed.review == []
    assert result.rows[1]["status"] == "review"  # the original result is unchanged


def test_reject_and_accept(session):
    result = session.get(["AMB", "FLAG"], have="protein.query", want="protein.name")
    by_input = {item.input: item for item in result.review}
    assert not by_input["FLAG"].ambiguous
    by_input["AMB"].reject()
    by_input["FLAG"].accept()
    resumed = result.resume()
    assert resumed["AMB"][0]["status"] == "unresolved"
    assert resumed["FLAG"][0]["protein.name"] == "Flagged name"


def test_review_choices_are_validated(session):
    result = session.get(["AMB", "FLAG"], have="protein.query", want="protein.name")
    amb, flag = sorted(result.review, key=lambda item: item.input)
    with pytest.raises(ValueError, match="candidate"):
        amb.choose(5)
    with pytest.raises(ValueError, match="choose"):
        amb.accept()
    with pytest.raises(ValueError, match="no candidates"):
        flag.choose(0)
    with pytest.raises(ValueError, match="no review decisions"):
        result.resume()


def test_async_resume(session):
    result = session.get(["AMB"], have="protein.query", want="protein.name")
    result.review[0].choose(0)
    resumed = asyncio.run(result.async_resume())
    assert resumed["AMB"][0]["protein.name"] == "Candidate A"


def test_session_cache_file_is_used(tmp_path):
    cache = tmp_path / "lookups.sqlite"
    with bw.Session(registry=_registry(), cache=cache) as s:
        s.get(["P1"], have="protein.query", want="protein.name")
    assert cache.exists()


# --- declared list totals ------------------------------------------------------


def test_rows_carry_listing(session):
    result = session.get(["P1", "MISS"], have="protein.query", want="structure.pdb.ids")
    assert result.columns == ["input", "row", "status", "structure.pdb.ids", "missing"]
    pdb = result.rows[0]["structure.pdb.ids"]
    assert isinstance(pdb, bw.Listing)
    assert pdb == ["ACC_P1-1", "ACC_P1-2"]
    assert (len(pdb), pdb.total, pdb.complete) == (2, 5, False)
    assert result.rows[1]["structure.pdb.ids"] is None
    assert "(2 of 5)" in repr(result)
    assert "(2 of 5)" in result._repr_html_()


def test_exports_add_total_column(session):
    result = session.get(["P1", "MISS"], have="protein.query", want="structure.pdb.ids")
    lines = result.to_csv().splitlines()
    assert lines[0] == "input,row,status,structure.pdb.ids,structure.pdb.ids.total,missing"
    assert lines[1].endswith(",ACC_P1-1; ACC_P1-2,5,")
    assert ",structure.pdb.ids," not in lines[2] and lines[2].split(",")[4] == ""


def test_record_totals_come_from_the_strands(session):
    result = session.get(["P1"], have="protein.query", want="structure.pdb.ids")
    assert result._records[0]["totals"] == {"structure.pdb.ids": {"total": 5, "complete": False}}


def test_no_total_column_without_a_declared_total(session):
    result = session.get(["P1"], have="protein.query", want="protein.name")
    assert "protein.name.total" not in result.columns


SET_CAP = Capability(
    id="list_structures",
    consumes=frozenset({"protein.uniprot.accession"}),
    produces=frozenset({"pdb.id"}),
    output_groups=(OutputGroup(id="g", outputs=frozenset({"pdb.id"})),),
    backends=("api",),
    set_outputs=frozenset({"pdb.id"}),
)


def _down_set(ss, backend, requested):
    return WeaveResult(
        "list_structures",
        "1.0.0",
        backend,
        frozenset({"g"}),
        status=WeaveStatus.OK,
        strands=(Strand("pdb.id", ["1ABC", "2DEF"], total=9, complete=False),),
    )


def test_fan_child_is_scalar():
    reg = BraidRegistry()
    reg.register(ScriptedWeaver(_up, capability=UP_CAP, weaver_id="uniprot"))
    reg.register(ScriptedWeaver(_down_set, capability=SET_CAP, weaver_id="pdbe"))
    with bw.Session(registry=reg) as s:
        result = s.get(["P1"], have="protein.query", want="pdb.id", expand="all")
    assert [row["pdb.id"] for row in result.rows] == ["1ABC", "2DEF"]
    assert all(type(row["pdb.id"]) is str for row in result.rows)
    assert all(row["parent"] for row in result.rows)


def test_partial_list_survives_resume(session):
    result = session.get(["AMB"], have="protein.query", want="structure.pdb.ids")
    result.review[0].choose(0)
    resumed = result.resume()
    pdb = resumed["AMB"][0]["structure.pdb.ids"]
    assert isinstance(pdb, bw.Listing) and (pdb.total, pdb.complete) == (5, False)
    assert "(2 of 5)" in repr(resumed)


def test_partial_list_survives_the_sqlite_cache(tmp_path):
    cache = tmp_path / "lookups.sqlite"
    reg = _registry()
    down = reg.get_weaver("pdbe")
    for attempt in range(2):
        with bw.Session(registry=reg, cache=cache) as s:
            result = s.get(["P1"], have="protein.query", want="structure.pdb.ids")
        pdb = result.rows[0]["structure.pdb.ids"]
        assert isinstance(pdb, bw.Listing) and (pdb.total, pdb.complete) == (5, False)
        if attempt == 0:
            calls_after_first = down.batch_calls
    assert down.batch_calls == calls_after_first  # second run read the cache


# --- a requested list comes back whole (#353) -------------------------------------

DESCRIBE_CAP = Capability(
    id="describe_structure",
    consumes=frozenset({"pdb.id"}),
    produces=frozenset({"structure.pdb.title"}),
    output_groups=(OutputGroup(id="g", outputs=frozenset({"structure.pdb.title"})),),
    backends=("api",),
)


def _describe(ss, backend, requested):
    pid = ss.get("pdb.id").value
    return WeaveResult(
        "describe_structure",
        "1.0.0",
        backend,
        frozenset({"g"}),
        status=WeaveStatus.OK,
        strands=(Strand("structure.pdb.title", f"Title of {pid}"),),
    )


def _set_registry():
    reg = BraidRegistry()
    reg.register(ScriptedWeaver(_up, capability=UP_CAP, weaver_id="uniprot"))
    reg.register(ScriptedWeaver(_down_set, capability=SET_CAP, weaver_id="pdbe"))
    reg.register(ScriptedWeaver(_describe, capability=DESCRIBE_CAP, weaver_id="pdbdesc"))
    return reg


def test_requested_set_output_comes_back_whole():
    with bw.Session(registry=_set_registry()) as s:
        result = s.get(["P1"], have="protein.query", want="pdb.id")
    assert len(result.rows) == 1
    ids = result.rows[0]["pdb.id"]
    assert isinstance(ids, bw.Listing) and ids == ["1ABC", "2DEF"]
    assert (ids.total, ids.complete) == (9, False)
    assert not any("auto-selected" in w for ss in result.raw.resolved for w in ss.warnings)


def test_set_output_a_later_step_consumes_still_collapses_to_one():
    with bw.Session(registry=_set_registry()) as s:
        result = s.get(["P1"], have="protein.query", want="structure.pdb.title")
    assert [row["structure.pdb.title"] for row in result.rows] == ["Title of 1ABC"]


def test_requested_set_output_comes_back_whole_after_resume():
    with bw.Session(registry=_set_registry()) as s:
        result = s.get(["AMB"], have="protein.query", want="pdb.id")
        result.review[0].choose(0)
        resumed = result.resume()
    ids = resumed["AMB"][0]["pdb.id"]
    assert isinstance(ids, bw.Listing) and ids == ["1ABC", "2DEF"]
