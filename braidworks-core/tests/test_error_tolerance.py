"""Error tolerance: a node failure is branch-local, classified, and rerouted-around.

A step ERROR no longer discards the whole entity. It is recorded (with a category +
plain-English reason), the entity's other branches keep running, and a fully-blocked
entity is rerouted around the failed node if the graph offers an alternate path —
otherwise it is reported. NO_MATCH stays valid data; only ErrorPolicy.RAISE aborts.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from braidworks.core import ErrorCategory, classify_error, explain_error
from braidworks.core.capability import Provenance
from braidworks.core.exceptions import BraidworksError
from braidworks.core.executor import ErrorPolicy, ExecutionResult, LocalExecutor
from braidworks.core.planner import Braider
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import Strand, StrandSet
from helpers import ScriptedWeaver, simple_capability


def _ok(cap_id: str, *strands: Strand) -> WeaveResult:
    return WeaveResult(cap_id, "1.0.0", "local", frozenset({"g"}),
                       status=WeaveStatus.OK, strands=tuple(strands))


def _err(cap_id: str, message: str) -> WeaveResult:
    return WeaveResult(cap_id, "1.0.0", "local", frozenset({"g"}),
                       status=WeaveStatus.ERROR, errors=(message,))


def _input(a: str = "A") -> list[StrandSet]:
    return [StrandSet.from_strands("e0", [Strand("a", a)])]


# --- classification ------------------------------------------------------------

@pytest.mark.parametrize("message,expected", [
    ("Server error '500 INTERNAL_SERVER_ERROR'", ErrorCategory.UPSTREAM_UNAVAILABLE),
    ("503 Service Unavailable", ErrorCategory.UPSTREAM_UNAVAILABLE),
    ("429 Too Many Requests", ErrorCategory.RATE_LIMITED),
    ("Read timeout after 30s", ErrorCategory.TIMEOUT),
    ("Connection refused", ErrorCategory.NETWORK),
    ("401 Unauthorized", ErrorCategory.AUTH),
    ("KeyError: 'reports'", ErrorCategory.BAD_RESPONSE),
    ("something weird", ErrorCategory.UNKNOWN),
    (None, ErrorCategory.UNKNOWN),
])
def test_classify_error(message, expected):
    assert classify_error(message) == expected


def test_explain_error_names_the_source():
    msg = explain_error(ErrorCategory.UPSTREAM_UNAVAILABLE, source="reactome")
    assert "reactome" in msg and "retry" in msg


# --- branch-local: a failed branch does not discard the good branches ----------

async def test_one_branch_errors_others_survive():
    reg = BraidRegistry()
    reg.register(ScriptedWeaver(
        lambda ss, b, r: _err("bad", "Server error '500'"),
        capability=simple_capability("bad", {"a"}, {"b"}), weaver_id="w_bad"))
    reg.register(ScriptedWeaver(
        lambda ss, b, r: _ok("good", Strand("c", "C")),
        capability=simple_capability("good", {"a"}, {"c"}), weaver_id="w_good"))

    braid = Braider(reg).plan(frozenset({"a"}), frozenset({"b", "c"}))
    res = await LocalExecutor(reg).execute(braid, _input())

    # the entity keeps the data the good branch produced — it is NOT discarded
    assert len(res.resolved) == 1
    assert res.resolved[0].get("c").value == "C"
    # the failed branch is reported and classified, but not fatal (entity resolved)
    assert len(res.errors) == 1
    assert res.errors[0].category is ErrorCategory.UPSTREAM_UNAVAILABLE
    assert res.fatal_errors() == []


# --- reroute: re-plan around a failed node via an alternate path ----------------

def _reroute_registry() -> BraidRegistry:
    """direct a->c (cost 1, errors) vs the alternate a->x->c (cost 2)."""
    reg = BraidRegistry()
    reg.register(ScriptedWeaver(
        lambda ss, b, r: _err("direct", "Server error '500'"),
        capability=simple_capability("direct", {"a"}, {"c"}, cost=1.0), weaver_id="w_direct"))
    reg.register(ScriptedWeaver(
        lambda ss, b, r: _ok("s1", Strand("x", "X")),
        capability=simple_capability("s1", {"a"}, {"x"}, cost=1.0), weaver_id="w_s1"))
    reg.register(ScriptedWeaver(
        lambda ss, b, r: _ok("s2", Strand("c", "C-via-x")),
        capability=simple_capability("s2", {"x"}, {"c"}, cost=1.0), weaver_id="w_s2"))
    return reg


async def test_reroutes_around_failed_node():
    reg = _reroute_registry()
    with_provenance = BraidRegistry()
    for wid in ("w_direct", "w_s1", "w_s2"):
        weaver = reg.get_weaver(wid)
        weaver._manifest = replace(weaver.MANIFEST,
            provenance=Provenance(source_url=f"https://{wid}.test", license="CC0-1.0"))
        with_provenance.register(weaver)
    reg = with_provenance
    braid = Braider(reg).plan(frozenset({"a"}), frozenset({"c"}))
    assert [s.capability_id for s in braid.steps] == ["direct"]  # cheapest path chosen first

    res = await LocalExecutor(reg).execute(braid, _input())
    assert [ref.weaver_id for ref in res.references] == ["w_direct", "w_s1", "w_s2"]

    # the direct node failed, but the weave rerouted a->x->c and reached the target
    assert len(res.resolved) == 1
    assert res.resolved[0].get("c").value == "C-via-x"
    # the original failure is still reported — but flagged recovered, so not fatal
    assert len(res.errors) == 1
    assert res.errors[0].recovered is True
    assert res.fatal_errors() == []


async def test_reroutes_onto_interchangeable_source():
    """Two weavers offer the SAME a->c edge (e.g. NCBI vs Ensembl taxonomy). The cheaper
    one is chosen; when it fails, reroute falls back onto the other producer."""
    reg = BraidRegistry()
    reg.register(ScriptedWeaver(
        lambda ss, b, r: _err("primary", "Server error '503'"),
        capability=simple_capability("primary", {"a"}, {"c"}, cost=1.0), weaver_id="ncbi"))
    reg.register(ScriptedWeaver(
        lambda ss, b, r: _ok("backup", Strand("c", "C-from-ensembl")),
        capability=simple_capability("backup", {"a"}, {"c"}, cost=2.0), weaver_id="ensembl"))

    braid = Braider(reg).plan(frozenset({"a"}), frozenset({"c"}))
    assert braid.steps[0].weaver_id == "ncbi"  # cheaper primary chosen

    res = await LocalExecutor(reg).execute(braid, _input())
    assert len(res.resolved) == 1
    assert res.resolved[0].get("c").value == "C-from-ensembl"  # fell back to the alternate source
    assert res.errors[0].recovered is True
    assert res.fatal_errors() == []


async def test_reroute_disabled_leaves_entity_blocked():
    reg = _reroute_registry()
    braid = Braider(reg).plan(frozenset({"a"}), frozenset({"c"}))
    res = await LocalExecutor(reg).execute(braid, _input(), reroute=False)
    assert res.resolved == []
    assert len(res.fatal_errors()) == 1  # no reroute → the error is fatal


async def test_no_alternate_path_reports_fatally():
    reg = BraidRegistry()
    reg.register(ScriptedWeaver(
        lambda ss, b, r: _err("only", "Server error '500'"),
        capability=simple_capability("only", {"a"}, {"c"}), weaver_id="w_only"))
    braid = Braider(reg).plan(frozenset({"a"}), frozenset({"c"}))
    res = await LocalExecutor(reg).execute(braid, _input())

    assert res.resolved == []
    assert len(res.errors) == 1
    assert res.errors[0].recovered is False
    assert len(res.fatal_errors()) == 1  # nothing to reroute to → reported


# --- RAISE still aborts; serialization round-trips the new fields ---------------

async def test_error_policy_raise_still_aborts():
    reg = BraidRegistry()
    reg.register(ScriptedWeaver(
        lambda ss, b, r: _err("only", "boom"),
        capability=simple_capability("only", {"a"}, {"c"}), weaver_id="w_only"))
    braid = Braider(reg).plan(frozenset({"a"}), frozenset({"c"}))
    with pytest.raises(BraidworksError):
        await LocalExecutor(reg).execute(braid, _input(), error_policy=ErrorPolicy.RAISE)


async def test_execution_error_json_roundtrip():
    from braidworks.core.executor import ExecutionError

    reg = BraidRegistry()
    reg.register(
        ScriptedWeaver(
            lambda ss, b, r: _err("only", "503 Service Unavailable"),
            capability=simple_capability("only", {"a"}, {"c"}),
            weaver_id="w_only",
        )
    )
    braid = Braider(reg).plan(frozenset({"a"}), frozenset({"c"}))
    res = await LocalExecutor(reg).execute(braid, _input())
    restored = ExecutionError.from_json(res.errors[0].to_json())
    assert restored.category is ErrorCategory.UPSTREAM_UNAVAILABLE
    assert restored.recovered is False


async def test_partial_success_accounting_survives_json_with_duplicate_entity_labels():
    reg = BraidRegistry()
    reg.register(
        ScriptedWeaver(
            lambda ss, b, r: _err("bad", "503 Service Unavailable"),
            capability=simple_capability("bad", {"a"}, {"b"}),
            weaver_id="bad",
        )
    )
    reg.register(
        ScriptedWeaver(
            lambda ss, b, r: (
                _ok("good", Strand("c", "C"))
                if ss.get("a").value == "success"
                else _err("good", "500")
            ),
            capability=simple_capability("good", {"a"}, {"c"}),
            weaver_id="good",
        )
    )
    inputs = [
        StrandSet.from_strands("same-label", [Strand("a", value)])
        for value in ("success", "failure")
    ]
    braid = Braider(reg).plan(frozenset({"a"}), frozenset({"b", "c"}))
    result = await LocalExecutor(reg).execute(braid, inputs, reroute=False)
    restored = ExecutionResult.from_json(json.loads(json.dumps(result.to_json())))
    assert len(result.resolved) == len(restored.resolved) == 1
    # Two failed branches on one input are diagnostics for ONE terminal entity.
    assert result.total() == restored.total() == 2
    assert len(result.fatal_errors()) == len(restored.fatal_errors()) == 2
    assert all(e.strand_set.get("a").value == "failure" for e in restored.fatal_errors())


async def test_identical_failed_inputs_remain_distinct_after_json():
    reg = BraidRegistry()
    for cap_id, output in (("bad1", "b"), ("bad2", "c")):
        reg.register(
            ScriptedWeaver(
                lambda ss, b, r, cid=cap_id: _err(cid, "503"),
                capability=simple_capability(cap_id, {"a"}, {output}),
                weaver_id=cap_id,
            )
        )
    braid = Braider(reg).plan(frozenset({"a"}), frozenset({"b", "c"}))
    result = await LocalExecutor(reg).execute(braid, _input() + _input(), reroute=False)
    restored = ExecutionResult.from_json(json.loads(json.dumps(result.to_json())))
    assert len(result.errors) == len(restored.errors) == 4
    assert result.total() == restored.total() == 2


async def test_recovered_error_is_not_an_additional_terminal_outcome():
    reg = _reroute_registry()
    braid = Braider(reg).plan(frozenset({"a"}), frozenset({"c"}))
    result = await LocalExecutor(reg).execute(braid, _input())
    restored = ExecutionResult.from_json(json.loads(json.dumps(result.to_json())))
    assert result.total() == restored.total() == 1
    assert restored.fatal_errors() == []


# --- exception classification + transient green-lighting -------------------------


class _FakeResp:
    def __init__(self, code):
        self.status_code = code


class _StatusErr(Exception):
    def __init__(self, code):
        self.response = _FakeResp(code)
        super().__init__("")


def test_classify_exception_by_type_even_with_empty_message():
    from braidworks.core import ErrorCategory, classify_exception

    class ReadTimeout(Exception):
        def __str__(self): return ""  # httpx timeouts stringify empty

    class ConnectError(Exception):
        def __str__(self): return ""

    assert classify_exception(ReadTimeout()) is ErrorCategory.TIMEOUT
    assert classify_exception(ConnectError()) is ErrorCategory.NETWORK
    assert classify_exception(_StatusErr(503)) is ErrorCategory.UPSTREAM_UNAVAILABLE
    assert classify_exception(_StatusErr(429)) is ErrorCategory.RATE_LIMITED
    assert classify_exception(_StatusErr(403)) is ErrorCategory.AUTH


def test_format_exc_is_never_empty_and_classifies():
    from braidworks.core import ErrorCategory, classify_error, format_exc

    class ReadTimeout(Exception):
        def __str__(self): return ""

    msg = format_exc(ReadTimeout())
    assert msg == "ReadTimeout"  # not empty
    assert classify_error(msg) is ErrorCategory.TIMEOUT  # the empty-message bug, fixed


def test_greenlightable_set_excludes_server_and_schema_errors():
    from braidworks.core import ErrorCategory as E
    from braidworks.core import is_greenlightable

    assert is_greenlightable(E.TIMEOUT)
    assert is_greenlightable(E.NETWORK)
    assert is_greenlightable(E.RATE_LIMITED)
    assert not is_greenlightable(E.UPSTREAM_UNAVAILABLE)  # 5xx → hard fail
    assert not is_greenlightable(E.BAD_RESPONSE)          # schema drift → hard fail
    assert not is_greenlightable(E.AUTH)


def test_skip_if_transient_skips_timeout_but_not_5xx():
    import pytest
    from braidworks.core import skip_if_transient
    from braidworks.core.result import WeaveResult, WeaveStatus

    timeout = WeaveResult("c", "1", "api", frozenset(),
                          status=WeaveStatus.ERROR, errors=("BacDive API error: ReadTimeout",))
    with pytest.raises(pytest.skip.Exception):
        skip_if_transient(timeout)

    server = WeaveResult("c", "1", "api", frozenset(),
                         status=WeaveStatus.ERROR, errors=("Server error '500'",))
    skip_if_transient(server)  # does NOT skip — a 5xx must fail loudly

    ok = WeaveResult("c", "1", "api", frozenset(), status=WeaveStatus.OK)
    skip_if_transient(ok)  # no-op
