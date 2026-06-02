"""LocalExecutor: preflight, guards, caching, fallback, review/error policies, chunking."""

from __future__ import annotations

import json

import pytest

from braidworks.core.braid import Braid, CapabilityInvocation, FallbackCondition
from braidworks.core.exceptions import (
    BackendConfigurationError,
    BackendUnavailable,
    BraidworksError,
    ReviewRequired,
)
from braidworks.core.executor import ErrorPolicy, LocalExecutor, ReviewPolicy
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import CandidateResult
from braidworks.core.strand import Strand, StrandSet

from helpers import (
    ScriptedWeaver,
    ambiguous_result,
    error_result,
    name_strand_sets,
    no_match_result,
    ok_result,
    resolve_name_capability,
    single_step_braid,
)

ID = "ncbi.taxon.id"
LINEAGE = "ncbi.taxon.lineage"
RANK = "ncbi.taxon.rank"


def _setup(resolver, *, capability=None):
    reg = BraidRegistry()
    weaver = ScriptedWeaver(resolver, capability=capability)
    reg.register(weaver)
    return reg, weaver, LocalExecutor(reg)


def _taxid_for(ss: StrandSet) -> int:
    # Deterministic fake taxid derived from the organism name.
    return abs(hash(ss.get("organism.name").value)) % 100_000


# --- happy path + caching ------------------------------------------------------

async def test_all_misses_resolve():
    reg, weaver, ex = _setup(lambda ss, b, r: ok_result(r, Strand(ID, _taxid_for(ss))))
    res = await ex.execute(single_step_braid({ID}), name_strand_sets("a", "b", "c"))
    assert len(res.resolved) == 3
    assert all(ss.has(ID) for ss in res.resolved)
    assert weaver.batch_calls == 1


async def test_second_pass_hits_cache():
    reg, weaver, ex = _setup(lambda ss, b, r: ok_result(r, Strand(ID, _taxid_for(ss))))
    braid = single_step_braid({ID})
    await ex.execute(braid, name_strand_sets("a", "b"))
    assert weaver.batch_calls == 1
    res2 = await ex.execute(braid, name_strand_sets("a", "b"))  # fresh sets, same values
    assert weaver.batch_calls == 1  # no new weaver calls
    assert len(res2.resolved) == 2


async def test_cache_superset_miss_for_richer_request():
    def resolver(ss, backend, requested):
        strands = [Strand(ID, _taxid_for(ss))]
        if LINEAGE in requested:
            strands.append(Strand(LINEAGE, [{"taxid": 1}]))
        return ok_result(requested, *strands)

    reg, weaver, ex = _setup(resolver)
    await ex.execute(single_step_braid({ID}), name_strand_sets("a"))  # caches {"core"}
    assert weaver.batch_calls == 1
    await ex.execute(single_step_braid({LINEAGE}), name_strand_sets("a"))  # needs lineage
    assert weaver.batch_calls == 2  # {"core"} does not cover {"core","lineage"}


async def test_third_pass_core_subset_hits_lineage_entry():
    def resolver(ss, backend, requested):
        strands = [Strand(ID, _taxid_for(ss))]
        if LINEAGE in requested:
            strands.append(Strand(LINEAGE, [{"taxid": 1}]))
        return ok_result(requested, *strands)

    reg, weaver, ex = _setup(resolver)
    await ex.execute(single_step_braid({LINEAGE}), name_strand_sets("a"))  # caches core+lineage
    assert weaver.batch_calls == 1
    await ex.execute(single_step_braid({RANK}), name_strand_sets("a"))  # core subset → hit
    assert weaver.batch_calls == 1


async def test_cached_no_match_routes_to_unresolved():
    reg, weaver, ex = _setup(lambda ss, b, r: no_match_result(r))
    braid = single_step_braid({ID})
    r1 = await ex.execute(braid, name_strand_sets("ghost"))
    assert len(r1.unresolved) == 1 and not r1.resolved
    r2 = await ex.execute(braid, name_strand_sets("ghost"))
    assert weaver.batch_calls == 1  # served from cache
    assert len(r2.unresolved) == 1 and not r2.resolved


async def test_cached_ambiguous_routes_to_review():
    reg, weaver, ex = _setup(lambda ss, b, r: ambiguous_result(r, CandidateResult(confidence=0.5)))
    braid = single_step_braid({ID})
    await ex.execute(braid, name_strand_sets("amb"))
    r2 = await ex.execute(braid, name_strand_sets("amb"))
    assert weaver.batch_calls == 1
    assert len(r2.review_queue) == 1


# --- preflight + guard ---------------------------------------------------------

async def test_preflight_missing_input_goes_to_errors():
    reg, weaver, ex = _setup(lambda ss, b, r: ok_result(r, Strand(ID, 1)))
    good = StrandSet.from_strands("g", [Strand("organism.name", "Homo sapiens")])
    bad = StrandSet.from_strands("b", [Strand("sample.id", "S-1")])  # no organism.name
    res = await ex.execute(single_step_braid({ID}), [good, bad])
    assert len(res.errors) == 1
    assert res.errors[0].error_type == "MissingInputError"
    assert res.errors[0].step_index is None
    assert len(res.resolved) == 1


async def test_guard1_skips_already_satisfied_entity():
    reg, weaver, ex = _setup(lambda ss, b, r: ok_result(r, Strand(ID, _taxid_for(ss))))
    pre = StrandSet.from_strands(
        "pre", [Strand("organism.name", "Homo sapiens"), Strand(ID, 9606)]
    )
    fresh = name_strand_sets("Mus musculus")[0]
    res = await ex.execute(single_step_braid({ID}), [pre, fresh])
    assert len(res.resolved) == 2
    # Only the fresh entity reached the weaver.
    assert weaver.batch_calls == 1 and weaver.batch_sizes == [1]


# --- outcome routing -----------------------------------------------------------

async def test_no_match_goes_to_unresolved_not_errors():
    reg, weaver, ex = _setup(lambda ss, b, r: no_match_result(r))
    res = await ex.execute(single_step_braid({ID}), name_strand_sets("ghost"))
    assert len(res.unresolved) == 1 and not res.errors and not res.resolved


async def test_ambiguous_halts_even_with_allow_continue():
    reg, weaver, ex = _setup(lambda ss, b, r: ambiguous_result(r, CandidateResult(confidence=0.6)))
    res = await ex.execute(
        single_step_braid({ID}), name_strand_sets("amb"), review_policy=ReviewPolicy.ALLOW_CONTINUE
    )
    assert len(res.review_queue) == 1 and not res.resolved


async def test_ambiguous_raise():
    reg, weaver, ex = _setup(lambda ss, b, r: ambiguous_result(r))
    with pytest.raises(ReviewRequired):
        await ex.execute(
            single_step_braid({ID}), name_strand_sets("amb"), review_policy=ReviewPolicy.RAISE
        )


async def test_ok_requires_review_allow_continue_resolves():
    reg, weaver, ex = _setup(
        lambda ss, b, r: ok_result(r, Strand(ID, _taxid_for(ss)), requires_review=True)
    )
    res = await ex.execute(
        single_step_braid({ID}), name_strand_sets("syn"), review_policy=ReviewPolicy.ALLOW_CONTINUE
    )
    assert len(res.resolved) == 1
    assert res.resolved[0].has(ID)
    assert res.resolved[0].requires_review is True


async def test_review_queue_item_remaining_steps():
    # Two-step braid; step 0 halts on requires_review, so remaining_steps == (step1,).
    step0 = single_step_braid({ID}).steps[0]
    step1 = CapabilityInvocation(
        weaver_id="other",
        capability_id="other.cap",
        input_types=frozenset({ID}),
        output_types=frozenset({"x.y"}),
        primary_backend="local",
    )
    braid = Braid(steps=(step0, step1), from_types=frozenset({"organism.name"}), to_types=frozenset({"x.y"}))
    reg, weaver, ex = _setup(
        lambda ss, b, r: ok_result(r, Strand(ID, 1), requires_review=True)
    )
    res = await ex.execute(braid, name_strand_sets("syn"))
    assert len(res.review_queue) == 1
    assert res.review_queue[0].remaining_steps == (step1,)


# --- backend failures + fallback ----------------------------------------------

async def test_backend_configuration_error_aborts_run():
    def resolver(ss, backend, requested):
        raise BackendConfigurationError("corrupt db")

    reg, weaver, ex = _setup(resolver)
    with pytest.raises(BackendConfigurationError):
        await ex.execute(single_step_braid({ID}), name_strand_sets("a", "b"))


async def test_backend_unavailable_retries_entire_batch_on_fallback():
    def resolver(ss, backend, requested):
        if backend == "local":
            raise BackendUnavailable("local not configured")
        return ok_result(requested, Strand(ID, _taxid_for(ss)), backend="api")

    cap = resolve_name_capability(backends=("local", "api"))
    reg, weaver, ex = _setup(resolver, capability=cap)
    braid = single_step_braid(
        {ID},
        primary="local",
        fallback_backends=("api",),
        fallback_on=frozenset({FallbackCondition.BACKEND_UNAVAILABLE}),
    )
    res = await ex.execute(braid, name_strand_sets("a", "b"))
    assert len(res.resolved) == 2
    assert weaver.batch_sizes == [2, 2]  # whole batch retried on api


async def test_error_fallback_retries_only_affected_entity():
    def resolver(ss, backend, requested):
        name = ss.get("organism.name").value
        if name == "bad" and backend == "local":
            return error_result(requested, "boom", backend="local")
        return ok_result(requested, Strand(ID, _taxid_for(ss)), backend=backend)

    cap = resolve_name_capability(backends=("local", "api"))
    reg, weaver, ex = _setup(resolver, capability=cap)
    braid = single_step_braid(
        {ID},
        primary="local",
        fallback_backends=("api",),
        fallback_on=frozenset({FallbackCondition.ERROR}),
    )
    res = await ex.execute(braid, name_strand_sets("good", "bad"))
    assert len(res.resolved) == 2
    assert weaver.batch_sizes == [2, 1]  # only the errored entity retried


async def test_no_match_fallback_retries_only_affected_entity():
    def resolver(ss, backend, requested):
        name = ss.get("organism.name").value
        if name == "nm" and backend == "local":
            return no_match_result(requested, backend="local")
        return ok_result(requested, Strand(ID, _taxid_for(ss)), backend=backend)

    cap = resolve_name_capability(backends=("local", "api"))
    reg, weaver, ex = _setup(resolver, capability=cap)
    braid = single_step_braid(
        {ID},
        primary="local",
        fallback_backends=("api",),
        fallback_on=frozenset({FallbackCondition.NO_MATCH}),
    )
    res = await ex.execute(braid, name_strand_sets("ok", "nm"))
    assert len(res.resolved) == 2
    assert weaver.batch_sizes == [2, 1]  # OK entity not re-resolved


# --- error policy --------------------------------------------------------------

async def test_error_record_and_continue():
    def resolver(ss, backend, requested):
        if ss.get("organism.name").value == "bad":
            return error_result(requested, "boom")
        return ok_result(requested, Strand(ID, _taxid_for(ss)))

    reg, weaver, ex = _setup(resolver)
    res = await ex.execute(single_step_braid({ID}), name_strand_sets("good", "bad"))
    assert len(res.resolved) == 1
    assert len(res.errors) == 1
    assert res.errors[0].capability_id == "ncbi.resolve_name"
    assert res.errors[0].step_index == 0


async def test_error_raise_aborts():
    reg, weaver, ex = _setup(lambda ss, b, r: error_result(r, "boom"))
    with pytest.raises(BraidworksError):
        await ex.execute(
            single_step_braid({ID}), name_strand_sets("bad"), error_policy=ErrorPolicy.RAISE
        )


async def test_execution_error_is_json_serializable():
    reg, weaver, ex = _setup(lambda ss, b, r: error_result(r, "boom"))
    res = await ex.execute(single_step_braid({ID}), name_strand_sets("bad"))
    json.dumps(res.errors[0].to_json())  # must not raise


# --- batching + chunking -------------------------------------------------------

async def test_max_batch_size_splits_calls():
    cap = resolve_name_capability(max_batch_size=3)
    reg, weaver, ex = _setup(
        lambda ss, b, r: ok_result(r, Strand(ID, _taxid_for(ss))), capability=cap
    )
    names = [f"n{i}" for i in range(10)]
    res = await ex.execute(single_step_braid({ID}), name_strand_sets(*names))
    assert weaver.batch_calls == 4
    assert weaver.batch_sizes == [3, 3, 3, 1]
    # Results reassembled in order: each entity carries its own derived taxid.
    by_entity = {ss.entity_id: ss.get(ID).value for ss in res.resolved}
    assert len(by_entity) == 10


async def test_chunking_three_chunks():
    reg, weaver, ex = _setup(lambda ss, b, r: ok_result(r, Strand(ID, _taxid_for(ss))))
    names = [f"n{i}" for i in range(25_000)]
    res = await ex.execute(
        single_step_braid({ID}), name_strand_sets(*names), chunk_size=10_000
    )
    assert len(res.resolved) == 25_000
    assert weaver.batch_calls == 3
    assert weaver.batch_sizes == [10_000, 10_000, 5_000]


# --- confidence threshold ------------------------------------------------------

async def test_confidence_threshold_halts():
    reg, weaver, ex = _setup(
        lambda ss, b, r: ok_result(r, Strand(ID, _taxid_for(ss), confidence=0.75))
    )
    res = await ex.execute(
        single_step_braid({ID}), name_strand_sets("low"), confidence_threshold=0.8
    )
    assert len(res.review_queue) == 1 and not res.resolved


async def test_confidence_and_review_independent_single_halt():
    reg, weaver, ex = _setup(
        lambda ss, b, r: ok_result(
            r, Strand(ID, _taxid_for(ss), confidence=0.75), requires_review=True
        )
    )
    # Both conditions true; HALT should produce exactly one queue item, not two.
    res = await ex.execute(
        single_step_braid({ID}), name_strand_sets("both"), confidence_threshold=0.8
    )
    assert len(res.review_queue) == 1
    # And with ALLOW_CONTINUE the entity resolves exactly once.
    reg2, weaver2, ex2 = _setup(
        lambda ss, b, r: ok_result(
            r, Strand(ID, _taxid_for(ss), confidence=0.75), requires_review=True
        )
    )
    res2 = await ex2.execute(
        single_step_braid({ID}),
        name_strand_sets("both"),
        confidence_threshold=0.8,
        review_policy=ReviewPolicy.ALLOW_CONTINUE,
    )
    assert len(res2.resolved) == 1


# --- exhaustiveness ------------------------------------------------------------

async def test_buckets_are_exhaustive_for_mixed_batch():
    def resolver(ss, backend, requested):
        name = ss.get("organism.name").value
        if name == "ok":
            return ok_result(requested, Strand(ID, 1))
        if name == "nm":
            return no_match_result(requested)
        if name == "amb":
            return ambiguous_result(requested, CandidateResult(confidence=0.5))
        return error_result(requested, "boom")  # name == "err"

    reg, weaver, ex = _setup(resolver)
    inputs = name_strand_sets("ok", "nm", "amb", "err")
    missing = StrandSet.from_strands("pf", [Strand("sample.id", "x")])  # preflight failure
    inputs.append(missing)
    res = await ex.execute(single_step_braid({ID}), inputs)
    assert len(res.resolved) == 1
    assert len(res.unresolved) == 1
    assert len(res.review_queue) == 1
    assert len(res.errors) == 2  # weaver ERROR + preflight MissingInputError
    assert res.total() == len(inputs)
