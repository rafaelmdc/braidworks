"""Cardinality fan-out (Phase 1): ExpandPolicy + resolver/entry expansion.

Covers the AMBIGUOUS-with-candidates path: TOP collapses to the best candidate,
TOP_K/ALL fork the entity into lineage-tagged children that continue the braid.
"""

from __future__ import annotations

import json

import pytest
from braidworks.core.braid import Braid, CapabilityInvocation
from braidworks.core.exceptions import ReviewRequired
from braidworks.core.executor import ExecutionResult, ExpandPolicy, LocalExecutor, ReviewPolicy
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import CandidateResult, WeaveResult, WeaveStatus
from braidworks.core.strand import Strand, StrandSet
from helpers import (
    ScriptedWeaver,
    ambiguous_result,
    name_strand_sets,
    simple_capability,
    single_step_braid,
)

ID = "ncbi.taxon.id"


def _setup(resolver, *, capability=None):
    reg = BraidRegistry()
    weaver = ScriptedWeaver(resolver, capability=capability)
    reg.register(weaver)
    return reg, weaver, LocalExecutor(reg)


def _cand(taxid: int, conf: float) -> CandidateResult:
    return CandidateResult(strands=(Strand(ID, taxid),), confidence=conf)


@pytest.mark.parametrize("expand", [ExpandPolicy.top(), ExpandPolicy.top_k(2), ExpandPolicy.all()])
async def test_explicit_raise_stops_ambiguous_candidates_before_expansion(expand):
    _, _, executor = _setup(lambda ss, b, r: ambiguous_result(r, _cand(1, 0.9), _cand(2, 0.4)))
    with pytest.raises(ReviewRequired, match="ambiguous"):
        await executor.execute(
            single_step_braid({ID}),
            name_strand_sets("amb"),
            expand_policy=expand,
            review_policy=ReviewPolicy.RAISE,
        )


@pytest.mark.parametrize("expand", [ExpandPolicy.top(), ExpandPolicy.all()])
async def test_candidate_confidence_threshold_halts_before_merging(expand):
    _, _, executor = _setup(lambda ss, b, r: ambiguous_result(r, _cand(1, 0.4)))
    result = await executor.execute(
        single_step_braid({ID}),
        name_strand_sets("amb"),
        expand_policy=expand,
        confidence_threshold=0.8,
    )
    assert not result.resolved
    assert len(result.review_queue) == 1
    assert result.review_queue[0].strand_set.get(ID) is None


async def test_auto_selected_ambiguity_retains_review_state_and_warnings_in_json():
    def resolver(ss, backend, requested):
        result = ambiguous_result(requested, _cand(1, 0.4))
        result.requires_review = True
        result.warnings = ("name needs curation",)
        return result

    _, _, executor = _setup(resolver)
    result = await executor.execute(
        single_step_braid({ID}),
        name_strand_sets("amb"),
        review_policy=ReviewPolicy.ALLOW_CONTINUE,
        confidence_threshold=0.3,
        expand_policy=ExpandPolicy.all(),
    )
    restored = ExecutionResult.from_json(json.loads(json.dumps(result.to_json())))
    assert restored.resolved[0].requires_review
    assert "name needs curation" in restored.resolved[0].warnings


# --- TOP (default): collapse to the single best candidate ----------------------


async def test_top_autopicks_best_candidate_and_resolves():
    # Explicit auto-selection + TOP merges the higher-confidence candidate.
    _reg, _weaver, ex = _setup(lambda ss, b, r: ambiguous_result(r, _cand(11, 0.6), _cand(22, 0.9)))
    res = await ex.execute(
        single_step_braid({ID}), name_strand_sets("amb"), review_policy=ReviewPolicy.ALLOW_CONTINUE
    )
    assert len(res.resolved) == 1 and not res.review_queue
    leaf = res.resolved[0]
    assert leaf.get(ID).value == 22  # highest confidence wins
    # Not silent: the discarded alternative is recorded as a warning.
    assert any("auto-selected 1 of 2" in w for w in leaf.warnings)


async def test_top_with_single_candidate_no_warning():
    _reg, _weaver, ex = _setup(lambda ss, b, r: ambiguous_result(r, _cand(7, 0.5)))
    res = await ex.execute(
        single_step_braid({ID}), name_strand_sets("amb"), review_policy=ReviewPolicy.ALLOW_CONTINUE
    )
    assert len(res.resolved) == 1
    assert res.resolved[0].warnings == []


# --- TOP_K / ALL: fork into independent children -------------------------------


async def test_top_k_forks_best_k_children():
    _reg, _weaver, ex = _setup(
        lambda ss, b, r: ambiguous_result(r, _cand(1, 0.3), _cand(2, 0.9), _cand(3, 0.6))
    )
    res = await ex.execute(
        single_step_braid({ID}),
        name_strand_sets("amb"),
        expand_policy=ExpandPolicy.top_k(2),
        review_policy=ReviewPolicy.ALLOW_CONTINUE,
    )
    assert len(res.resolved) == 2
    values = sorted(leaf.get(ID).value for leaf in res.resolved)
    assert values == [2, 3]  # the two highest-confidence candidates


async def test_all_forks_every_candidate():
    _reg, _weaver, ex = _setup(
        lambda ss, b, r: ambiguous_result(r, _cand(1, 0.3), _cand(2, 0.9), _cand(3, 0.6))
    )
    res = await ex.execute(
        single_step_braid({ID}),
        name_strand_sets("amb"),
        expand_policy=ExpandPolicy.all(),
        review_policy=ReviewPolicy.ALLOW_CONTINUE,
    )
    assert len(res.resolved) == 3
    assert sorted(leaf.get(ID).value for leaf in res.resolved) == [1, 2, 3]


async def test_fanout_children_carry_lineage_to_original_input():
    _reg, _weaver, ex = _setup(lambda ss, b, r: ambiguous_result(r, _cand(1, 0.9), _cand(2, 0.5)))
    res = await ex.execute(
        single_step_braid({ID}),
        name_strand_sets("amb"),
        expand_policy=ExpandPolicy.all(),
        review_policy=ReviewPolicy.ALLOW_CONTINUE,
    )
    # name_strand_sets builds entity_id "e0"; children regroup to that root.
    assert {leaf.parent_id for leaf in res.resolved} == {"e0"}
    assert sorted(leaf.entity_id for leaf in res.resolved) == ["e0#0", "e0#1"]


# --- forked children continue through the remaining waves ----------------------


async def test_forked_children_continue_to_next_wave():
    # step0 forks on the candidate set; step1 must run over EACH child.
    reg = BraidRegistry()
    reg.register(
        ScriptedWeaver(lambda ss, b, r: ambiguous_result(r, _cand(10, 0.9), _cand(20, 0.5)))
    )

    def enrich(ss, backend, requested):
        tid = ss.get(ID).value
        return WeaveResult(
            capability_id="enrich.cap",
            weaver_version="1.0.0",
            backend_used=backend,
            computed_groups=frozenset({"g"}),
            status=WeaveStatus.OK,
            strands=(Strand("x.y", f"v{tid}"),),
        )

    reg.register(
        ScriptedWeaver(
            enrich,
            capability=simple_capability("enrich.cap", {ID}, {"x.y"}),
            weaver_id="enrich",
        )
    )
    step0 = CapabilityInvocation(
        weaver_id="ncbi",
        capability_id="ncbi.resolve_name",
        input_types=frozenset({"organism.name"}),
        output_types=frozenset({ID}),
        primary_backend="local",
    )
    step1 = CapabilityInvocation(
        weaver_id="enrich",
        capability_id="enrich.cap",
        input_types=frozenset({ID}),
        output_types=frozenset({"x.y"}),
        primary_backend="local",
    )
    braid = Braid(
        steps=(step0, step1),
        from_types=frozenset({"organism.name"}),
        to_types=frozenset({"x.y"}),
    )
    res = await LocalExecutor(reg).execute(
        braid,
        name_strand_sets("amb"),
        expand_policy=ExpandPolicy.all(),
        review_policy=ReviewPolicy.ALLOW_CONTINUE,
    )
    assert len(res.resolved) == 2
    assert sorted(leaf.get("x.y").value for leaf in res.resolved) == ["v10", "v20"]


# --- guardrails + interactions -------------------------------------------------


async def test_max_expansion_caps_blowup():
    cands = tuple(_cand(i, 1.0 - i / 100) for i in range(5))
    _reg, _weaver, ex = _setup(lambda ss, b, r: ambiguous_result(r, *cands))
    res = await ex.execute(
        single_step_braid({ID}),
        name_strand_sets("amb"),
        expand_policy=ExpandPolicy.all(),
        max_expansion=2,
        review_policy=ReviewPolicy.ALLOW_CONTINUE,
    )
    assert len(res.resolved) == 2  # capped from 5
    assert (res.truncations[0].requested, res.truncations[0].omitted) == (5, 3)


async def test_no_candidate_ambiguous_still_reviews_under_all():
    # ExpandPolicy never overrides the review path when there is nothing to fork.
    _reg, _weaver, ex = _setup(lambda ss, b, r: ambiguous_result(r))
    res = await ex.execute(
        single_step_braid({ID}),
        name_strand_sets("amb"),
        review_policy=ReviewPolicy.HALT,
        expand_policy=ExpandPolicy.all(),
    )
    assert len(res.review_queue) == 1 and not res.resolved


async def test_fork_value_in_cache_key_keeps_children_distinct():
    # Each child carries a distinct fan value, so a downstream cache cannot collide them.
    _reg, _weaver, ex = _setup(lambda ss, b, r: ambiguous_result(r, _cand(1, 0.9), _cand(2, 0.8)))
    res = await ex.execute(
        single_step_braid({ID}),
        name_strand_sets("amb"),
        expand_policy=ExpandPolicy.all(),
        review_policy=ReviewPolicy.ALLOW_CONTINUE,
    )
    ids = [leaf.get(ID).value for leaf in res.resolved]
    assert sorted(ids) == [1, 2] and len(set(ids)) == 2


# --- lineage round-trips through JSON ------------------------------------------


def test_parent_id_survives_json_roundtrip():
    child = StrandSet.from_strands("e0#1", [Strand(ID, 5)])
    child.parent_id = "e0"
    restored = StrandSet.from_json(child.to_json())
    assert restored.parent_id == "e0"


def test_default_strand_set_has_no_parent():
    assert StrandSet.from_strands("e0", []).parent_id is None


@pytest.mark.parametrize("expand", [ExpandPolicy.top(), ExpandPolicy.top_k(2), ExpandPolicy.all()])
@pytest.mark.parametrize("threshold", [0.0, 0.8])
async def test_default_review_halts_ambiguity_before_selection_or_fanout(expand, threshold):
    _, _, executor = _setup(lambda ss, b, r: ambiguous_result(r, _cand(1, 0.95), _cand(2, 0.9)))
    inputs = name_strand_sets("amb")
    result = await executor.execute(
        single_step_braid({ID}), inputs, expand_policy=expand, confidence_threshold=threshold
    )
    assert not result.resolved and not result.unresolved and not result.errors
    assert len(result.review_queue) == 1 and not result.truncations
    item = result.review_queue[0]
    assert item.strand_set is inputs[0] and item.strand_set.get(ID) is None
    assert len(item.triggering_result.candidates) == 2
    restored = ExecutionResult.from_json(json.loads(json.dumps(result.to_json())))
    assert len(restored.review_queue[0].triggering_result.candidates) == 2


async def test_auto_selection_cannot_override_explicit_confidence_floor():
    _, _, executor = _setup(lambda ss, b, r: ambiguous_result(r, _cand(1, 0.4)))
    result = await executor.execute(
        single_step_braid({ID}),
        name_strand_sets("amb"),
        review_policy=ReviewPolicy.ALLOW_CONTINUE,
        confidence_threshold=0.8,
    )
    assert not result.resolved and len(result.review_queue) == 1
    assert result.review_queue[0].strand_set.get(ID) is None


async def test_cached_ambiguity_obeys_each_calls_review_policy():
    _, weaver, executor = _setup(lambda ss, b, r: ambiguous_result(r, _cand(1, 0.9), _cand(2, 0.7)))
    braid = single_step_braid({ID})
    paused = await executor.execute(braid, name_strand_sets("amb"))
    selected = await executor.execute(
        braid, name_strand_sets("amb"), review_policy=ReviewPolicy.ALLOW_CONTINUE
    )
    paused_again = await executor.execute(braid, name_strand_sets("amb"))
    assert len(paused.review_queue) == len(paused_again.review_queue) == 1
    assert selected.resolved[0].get(ID).value == 1 and selected.resolved[0].requires_review
    assert len(paused_again.review_queue[0].triggering_result.candidates) == 2
    assert weaver.batch_calls == 1
