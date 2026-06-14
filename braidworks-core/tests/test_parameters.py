"""Tests for the per-capability parameter channel — model, defaults, validation,
the cache-key fold, and end-to-end threading through the executor."""

from __future__ import annotations

import pytest

from braidworks.core import (
    BraidRegistry,
    Braider,
    Capability,
    LocalExecutor,
    OutputGroup,
    Parameter,
    Strand,
    StrandSet,
)
from braidworks.core.cache import compute_cache_key
from braidworks.core.result import WeaveResult, WeaveStatus

from tests.helpers import ScriptedWeaver


# --- Parameter model ---------------------------------------------------------------

def test_parameter_coercion_by_type():
    assert Parameter("n", type="int").coerce("5") == 5
    assert Parameter("x", type="float").coerce("1.5") == 1.5
    assert Parameter("b", type="bool").coerce("true") is True
    assert Parameter("b", type="bool").coerce("0") is False
    assert Parameter("s").coerce(42) == "42"


def test_parameter_rejects_unknown_type():
    with pytest.raises(ValueError):
        Parameter("p", type="date")


def test_parameter_default_must_be_in_enum():
    with pytest.raises(ValueError):
        Parameter("p", enum=("a", "b"), default="c")


def test_parameter_validate_checks_enum():
    p = Parameter("level", enum=("complete", "contig"))
    assert p.validate("complete") == "complete"
    with pytest.raises(ValueError):
        p.validate("scaffold")


def _cap(**kw):
    return Capability(
        id="op", consumes=frozenset({"a"}), produces=frozenset({"b"}),
        output_groups=(OutputGroup(id="g", outputs=frozenset({"b"})),), backends=("api",),
        **kw,
    )


def test_resolve_params_applies_defaults_and_overrides():
    cap = _cap(parameters=(
        Parameter("level", enum=("complete", "contig"), default="complete"),
        Parameter("limit", type="int", default=10),
        Parameter("flag", type="bool"),  # no default -> absent unless given
    ))
    assert cap.resolve_params(None) == {"level": "complete", "limit": 10}
    assert cap.resolve_params({"limit": "3", "flag": "yes"}) == {
        "level": "complete", "limit": 3, "flag": True,
    }


def test_resolve_params_rejects_unknown_name():
    cap = _cap(parameters=(Parameter("level"),))
    with pytest.raises(ValueError):
        cap.resolve_params({"bogus": 1})


def test_capability_rejects_duplicate_parameter_names():
    with pytest.raises(ValueError):
        _cap(parameters=(Parameter("x"), Parameter("x")))


def test_capability_parameters_roundtrip_json():
    cap = _cap(parameters=(Parameter("level", enum=("a", "b"), default="a", description="d"),))
    assert Capability.from_json(cap.to_json()) == cap


# --- cache key fold ----------------------------------------------------------------

def test_cache_key_differs_by_params():
    cap = _cap(parameters=(Parameter("level"),))
    ss = StrandSet.from_strands("e1", [Strand("a", "x")])
    common = dict(weaver_id="w", weaver_version="1", backend="api", backend_fingerprint="fp")
    k_none = compute_cache_key(cap, ss, **common)
    k_a = compute_cache_key(cap, ss, params={"level": "complete"}, **common)
    k_b = compute_cache_key(cap, ss, params={"level": "contig"}, **common)
    assert k_none != k_a != k_b and k_a != k_b
    # same effective params -> same key (deterministic)
    assert k_a == compute_cache_key(cap, ss, params={"level": "complete"}, **common)


# --- end-to-end through the executor -----------------------------------------------

PARAM_CAP = Capability(
    id="op", consumes=frozenset({"a"}), produces=frozenset({"b"}),
    output_groups=(OutputGroup(id="g", outputs=frozenset({"b"})),), backends=("api",),
    parameters=(Parameter("scale", type="int", default=1),),
)


def test_executor_threads_effective_params_to_the_weaver():
    received: list[dict] = []

    class Recorder(ScriptedWeaver):
        async def execute_batch(self, capability_id, strand_sets, *, requested_outputs,
                                backend, params=None):
            received.append(params)
            base = (params or {}).get("scale", 1)
            return [
                WeaveResult("op", "1.0.0", backend, frozenset({"g"}), status=WeaveStatus.OK,
                            strands=(Strand("b", int(ss.get("a").value) * base),))
                for ss in strand_sets
            ]

    weaver = Recorder(lambda *a: None, capability=PARAM_CAP, weaver_id="w")
    reg = BraidRegistry()
    reg.register(weaver)
    braid = Braider(reg).plan(available_types=frozenset({"a"}), target_types=frozenset({"b"}))

    # Fresh inputs per run — execute() merges results into the StrandSet in place.
    def fresh():
        return [StrandSet.from_strands("e1", [Strand("a", "10")])]

    import asyncio
    # default param applied
    out = asyncio.run(LocalExecutor(reg).execute(braid, fresh()))
    assert out.resolved[0].get("b").value == 10
    assert received[-1] == {"scale": 1}
    # caller override flows through and changes the result
    out = asyncio.run(LocalExecutor(reg).execute(braid, fresh(), params={"op": {"scale": "3"}}))
    assert out.resolved[0].get("b").value == 30
    assert received[-1] == {"scale": 3}


def test_executor_rejects_unknown_param():
    import asyncio
    weaver = ScriptedWeaver(lambda ss, b, r: None, capability=PARAM_CAP, weaver_id="w")
    reg = BraidRegistry()
    reg.register(weaver)
    braid = Braider(reg).plan(available_types=frozenset({"a"}), target_types=frozenset({"b"}))
    sets = [StrandSet.from_strands("e1", [Strand("a", "1")])]
    with pytest.raises(ValueError):
        asyncio.run(LocalExecutor(reg).execute(braid, sets, params={"op": {"bogus": 1}}))
