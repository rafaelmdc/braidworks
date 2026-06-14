"""Cardinality fan-out (Phase 2): mid-braid set-output expansion.

A capability may declare a produced join key as ``set_outputs`` (one→many). When the
weaver emits that key as a *list*, the executor forks the entity per value under
``TOP_K``/``ALL`` (or collapses to a representative under ``TOP``), reusing the Phase-1
lineage scheme. ``expand_by_type`` overrides the policy per join key.
"""

from __future__ import annotations

from braidworks.core.braid import Braid, CapabilityInvocation
from braidworks.core.capability import Capability, OutputGroup
from braidworks.core.executor import ExpandPolicy, LocalExecutor
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import Strand, StrandSet

from helpers import ScriptedWeaver, simple_capability

INPUT = "protein.uniprot.accession"
PATHWAY = "pathway.reactome.id"
PDB = "pdb.id"
CAP = "reactome.pathways"


def _set_cap(produces, set_outputs, *, cap_id=CAP, consumes=(INPUT,)) -> Capability:
    produces = frozenset(produces)
    return Capability(
        id=cap_id,
        consumes=frozenset(consumes),
        produces=produces,
        output_groups=(OutputGroup(id="g", outputs=produces),),
        backends=("local",),
        set_outputs=frozenset(set_outputs),
    )


def _ok(*strands, cap_id=CAP) -> WeaveResult:
    return WeaveResult(
        capability_id=cap_id,
        weaver_version="1.0.0",
        backend_used="local",
        computed_groups=frozenset({"g"}),
        status=WeaveStatus.OK,
        strands=tuple(strands),
    )


def _setup(resolver, capability):
    reg = BraidRegistry()
    reg.register(ScriptedWeaver(resolver, capability=capability))
    return reg, LocalExecutor(reg)


def _inputs(*accessions):
    return [StrandSet.from_strands(f"e{i}", [Strand(INPUT, a)]) for i, a in enumerate(accessions)]


def _one_step(output_types):
    inv = CapabilityInvocation(
        weaver_id="ncbi",
        capability_id=CAP,
        input_types=frozenset({INPUT}),
        output_types=frozenset(output_types),
        primary_backend="local",
    )
    return Braid(
        steps=(inv,), from_types=frozenset({INPUT}), to_types=frozenset(output_types)
    )


# --- TOP (default): collapse a set output to a representative -------------------

async def test_top_collapses_set_output_in_place():
    cap = _set_cap({PATHWAY}, {PATHWAY})
    reg, ex = _setup(lambda ss, b, r: _ok(Strand(PATHWAY, ["R-3", "R-1", "R-2"])), cap)
    res = await ex.execute(_one_step({PATHWAY}), _inputs("P1"))  # default ExpandPolicy.TOP
    assert len(res.resolved) == 1
    leaf = res.resolved[0]
    assert leaf.get(PATHWAY).value == "R-3"  # first (best-first) representative, scalar
    assert any("auto-selected 1 of 3" in w for w in leaf.warnings)


async def test_set_output_same_as_consumed_key_forks_on_produced_list():
    # A capability that consumes AND produces the same key (e.g. taxid -> child taxids):
    # the produced list must win over the input scalar so it can fan (regression). The
    # target is a *different* output ("n") so the step isn't skipped as already-satisfied.
    cap = _set_cap({INPUT, "n"}, {INPUT}, consumes=(INPUT,))
    reg, ex = _setup(
        lambda ss, b, r: _ok(Strand(INPUT, ["c1", "c2", "c3"]), Strand("n", 3)), cap
    )
    res = await ex.execute(_one_step({INPUT, "n"}), _inputs("parent"),
                           expand_policy=ExpandPolicy.all())
    assert len(res.resolved) == 3
    assert {leaf.get(INPUT).value for leaf in res.resolved} == {"c1", "c2", "c3"}
    assert all(leaf.parent_id == "e0" for leaf in res.resolved)


# --- ALL / TOP_K: fork per value -----------------------------------------------

async def test_all_forks_one_child_per_value():
    cap = _set_cap({PATHWAY}, {PATHWAY})
    reg, ex = _setup(lambda ss, b, r: _ok(Strand(PATHWAY, ["R-1", "R-2", "R-3"])), cap)
    res = await ex.execute(_one_step({PATHWAY}), _inputs("P1"), expand_policy=ExpandPolicy.all())
    assert len(res.resolved) == 3
    assert sorted(leaf.get(PATHWAY).value for leaf in res.resolved) == ["R-1", "R-2", "R-3"]
    # each leaf carries a scalar, lineage points at the originating input, ids nest.
    assert all(isinstance(leaf.get(PATHWAY).value, str) for leaf in res.resolved)
    assert {leaf.parent_id for leaf in res.resolved} == {"e0"}
    assert sorted(leaf.entity_id for leaf in res.resolved) == ["e0#0", "e0#1", "e0#2"]


async def test_top_k_keeps_best_k():
    cap = _set_cap({PATHWAY}, {PATHWAY})
    reg, ex = _setup(lambda ss, b, r: _ok(Strand(PATHWAY, ["R-1", "R-2", "R-3", "R-4"])), cap)
    res = await ex.execute(_one_step({PATHWAY}), _inputs("P1"), expand_policy=ExpandPolicy.top_k(2))
    assert sorted(leaf.get(PATHWAY).value for leaf in res.resolved) == ["R-1", "R-2"]


async def test_expand_by_type_overrides_default():
    cap = _set_cap({PATHWAY}, {PATHWAY})
    reg, ex = _setup(lambda ss, b, r: _ok(Strand(PATHWAY, ["R-1", "R-2"])), cap)
    res = await ex.execute(
        _one_step({PATHWAY}),
        _inputs("P1"),
        expand_policy=ExpandPolicy.top(),  # global default would collapse
        expand_by_type={PATHWAY: ExpandPolicy.all()},  # but this key fans
    )
    assert len(res.resolved) == 2


async def test_single_value_set_output_does_not_fork():
    cap = _set_cap({PATHWAY}, {PATHWAY})
    reg, ex = _setup(lambda ss, b, r: _ok(Strand(PATHWAY, ["R-only"])), cap)
    res = await ex.execute(_one_step({PATHWAY}), _inputs("P1"), expand_policy=ExpandPolicy.all())
    assert len(res.resolved) == 1
    assert res.resolved[0].entity_id == "e0"  # no spurious "#0" child
    assert res.resolved[0].get(PATHWAY).value == "R-only"


# --- cross-product of two set dimensions ---------------------------------------

async def test_two_set_dimensions_cross_product():
    cap = _set_cap({PATHWAY, PDB}, {PATHWAY, PDB})
    reg, ex = _setup(
        lambda ss, b, r: _ok(Strand(PATHWAY, ["R-1", "R-2"]), Strand(PDB, ["1ABC", "2XYZ"])), cap
    )
    res = await ex.execute(_one_step({PATHWAY, PDB}), _inputs("P1"), expand_policy=ExpandPolicy.all())
    assert len(res.resolved) == 4  # 2 × 2
    combos = sorted((leaf.get(PATHWAY).value, leaf.get(PDB).value) for leaf in res.resolved)
    assert combos == [("R-1", "1ABC"), ("R-1", "2XYZ"), ("R-2", "1ABC"), ("R-2", "2XYZ")]


async def test_mixed_policy_per_dimension():
    cap = _set_cap({PATHWAY, PDB}, {PATHWAY, PDB})
    reg, ex = _setup(
        lambda ss, b, r: _ok(Strand(PATHWAY, ["R-1", "R-2"]), Strand(PDB, ["1ABC", "2XYZ"])), cap
    )
    res = await ex.execute(
        _one_step({PATHWAY, PDB}),
        _inputs("P1"),
        expand_by_type={PATHWAY: ExpandPolicy.all(), PDB: ExpandPolicy.top()},
    )
    assert len(res.resolved) == 2  # PATHWAY fans ×2, PDB collapses to its representative
    assert sorted(leaf.get(PATHWAY).value for leaf in res.resolved) == ["R-1", "R-2"]
    assert {leaf.get(PDB).value for leaf in res.resolved} == {"1ABC"}


# --- forked children continue through later waves ------------------------------

async def test_set_fork_children_continue_to_next_wave():
    reg = BraidRegistry()
    reg.register(ScriptedWeaver(lambda ss, b, r: _ok(Strand(PATHWAY, ["R-1", "R-2"])), capability=_set_cap({PATHWAY}, {PATHWAY})))

    def detail(ss, backend, requested):
        pid = ss.get(PATHWAY).value
        return WeaveResult(
            capability_id="reactome.detail",
            weaver_version="1.0.0",
            backend_used=backend,
            computed_groups=frozenset({"g"}),
            status=WeaveStatus.OK,
            strands=(Strand("pathway.reactome.names", f"name-of-{pid}"),),
        )

    reg.register(
        ScriptedWeaver(
            detail,
            capability=simple_capability("reactome.detail", {PATHWAY}, {"pathway.reactome.names"}),
            weaver_id="detail",
        )
    )
    step0 = CapabilityInvocation(
        weaver_id="ncbi", capability_id=CAP,
        input_types=frozenset({INPUT}), output_types=frozenset({PATHWAY}), primary_backend="local",
    )
    step1 = CapabilityInvocation(
        weaver_id="detail", capability_id="reactome.detail",
        input_types=frozenset({PATHWAY}), output_types=frozenset({"pathway.reactome.names"}),
        primary_backend="local",
    )
    braid = Braid(
        steps=(step0, step1),
        from_types=frozenset({INPUT}),
        to_types=frozenset({"pathway.reactome.names"}),
    )
    res = await LocalExecutor(reg).execute(braid, _inputs("P1"), expand_policy=ExpandPolicy.all())
    assert len(res.resolved) == 2
    assert sorted(leaf.get("pathway.reactome.names").value for leaf in res.resolved) == [
        "name-of-R-1",
        "name-of-R-2",
    ]


# --- guardrail -----------------------------------------------------------------

async def test_max_expansion_caps_set_fork():
    cap = _set_cap({PATHWAY}, {PATHWAY})
    reg, ex = _setup(lambda ss, b, r: _ok(Strand(PATHWAY, [f"R-{i}" for i in range(6)])), cap)
    res = await ex.execute(
        _one_step({PATHWAY}), _inputs("P1"), expand_policy=ExpandPolicy.all(), max_expansion=3
    )
    assert len(res.resolved) == 3  # capped from 6


# --- declaration validity + serialization --------------------------------------

def test_set_outputs_must_subset_produces():
    import pytest

    with pytest.raises(ValueError):
        _set_cap({PATHWAY}, {PDB})  # PDB not in produces


def test_capability_set_outputs_json_roundtrip():
    cap = _set_cap({PATHWAY, PDB}, {PATHWAY})
    restored = Capability.from_json(cap.to_json())
    assert restored.set_outputs == frozenset({PATHWAY})
