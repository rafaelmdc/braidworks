"""Entity-level fan-out: planning, the fail-safe, and the runner split/gather."""

from __future__ import annotations

import pytest

from braidworks_arq import discovery
from braidworks_arq.executor import build_distributed_executor
from braidworks_arq.fanout import FanoutConfigError, FanoutPlan, plan_fanout
from braidworks_arq.runner import ArqStepRunner
from braidworks_arq.tasks import weave_step

from fakes import (
    TAXID,
    EchoWeaver,
    InlineJob,
    name_sets,
    registry_with,
    single_step_braid,
)


# --- planning -----------------------------------------------------------------


def test_no_fanout_by_default():
    plan = plan_fanout("ncbi", "local", 100, widths={}, unbudgeted=set(), chunks={}, budgeted=False)
    assert plan == FanoutPlan(width=1, chunk=100)


def test_budgeted_backend_uses_chunk_one():
    plan = plan_fanout(
        "ncbi", "api", 100, widths={"ncbi:api": 4}, unbudgeted=set(), chunks={}, budgeted=True
    )
    assert plan.width == 4 and plan.chunk == 1


def test_unbudgeted_local_splits_evenly():
    plan = plan_fanout(
        "ncbi", "local", 100, widths={"ncbi:local": 4}, unbudgeted={"ncbi:local"}, chunks={}, budgeted=False
    )
    assert plan.width == 4 and plan.chunk == 25  # ceil(100/4)


def test_explicit_chunk_override_wins():
    plan = plan_fanout(
        "ncbi", "local", 100, widths={"ncbi": 4}, unbudgeted={"ncbi"}, chunks={"ncbi:local": 10}, budgeted=False
    )
    assert plan.width == 4 and plan.chunk == 10


def test_fanout_without_budget_or_assertion_raises():
    with pytest.raises(FanoutConfigError, match="no rate budget"):
        plan_fanout("ncbi", "api", 100, widths={"ncbi:api": 4}, unbudgeted=set(), chunks={}, budgeted=False)


def test_backend_specific_width_beats_bare_weaver():
    plan = plan_fanout(
        "ncbi", "local", 50,
        widths={"ncbi": 2, "ncbi:local": 5}, unbudgeted={"ncbi:local"}, chunks={}, budgeted=False,
    )
    assert plan.width == 5


# --- runner fan-out (inline, no Redis) ----------------------------------------


class CountingPool:
    """Inline pool that records the size of each dispatched chunk."""

    def __init__(self, fn) -> None:
        self._fn = fn
        self.chunk_sizes: list[int] = []

    async def enqueue_job(self, name, weaver_id, cap, backend, payload, requested,
                          params=None, _queue_name=None):
        self.chunk_sizes.append(len(payload))
        return InlineJob(
            self._fn, (weaver_id, cap, backend, payload, requested, params), None
        )


async def test_runner_fans_out_and_preserves_order(monkeypatch):
    monkeypatch.setenv("BRAIDWORKS_FANOUT", "fake:local=3")
    monkeypatch.setenv("BRAIDWORKS_FANOUT_UNBUDGETED", "fake:local")
    discovery.set_registry(registry_with(EchoWeaver()))
    pool = CountingPool(weave_step)
    runner = ArqStepRunner(pool=pool)

    sets = name_sets("a", "b", "c", "d", "e")
    results = await runner.run_step("fake", "fake.resolve", "local", sets, frozenset({TAXID}))

    # One result per input, aligned to input order (each name → its own taxid).
    assert len(results) == 5
    expected = [abs(hash(s.get("organism.name").value)) % 100_000 for s in sets]
    assert [r.strands[0].value for r in results] == expected
    # Batch of 5, chunk ceil(5/3)=2 → chunks of [2, 2, 1] across 3 jobs.
    assert sorted(pool.chunk_sizes) == [1, 2, 2]


async def test_runner_no_fanout_is_single_dispatch(monkeypatch):
    monkeypatch.delenv("BRAIDWORKS_FANOUT", raising=False)
    discovery.set_registry(registry_with(EchoWeaver()))
    pool = CountingPool(weave_step)
    runner = ArqStepRunner(pool=pool)
    await runner.run_step("fake", "fake.resolve", "local", name_sets("a", "b", "c"), frozenset({TAXID}))
    assert pool.chunk_sizes == [3]  # one job, whole batch


async def test_executor_fans_out_bulk_local(monkeypatch):
    monkeypatch.setenv("BRAIDWORKS_FANOUT", "fake:local=4")
    monkeypatch.setenv("BRAIDWORKS_FANOUT_UNBUDGETED", "fake:local")
    weaver = EchoWeaver()
    reg = registry_with(weaver)
    discovery.set_registry(reg)
    pool = CountingPool(weave_step)
    ex = build_distributed_executor(reg, pool=pool)
    res = await ex.execute(single_step_braid(), name_sets(*[f"org{i}" for i in range(10)]))
    assert len(res.resolved) == 10
    assert len(pool.chunk_sizes) > 1  # the batch was fanned across multiple jobs


async def test_executor_fanout_without_budget_raises(monkeypatch):
    monkeypatch.setenv("BRAIDWORKS_FANOUT", "fake:local=4")
    monkeypatch.delenv("BRAIDWORKS_FANOUT_UNBUDGETED", raising=False)
    monkeypatch.delenv("BRAIDWORKS_RATE_LIMITS", raising=False)
    reg = registry_with(EchoWeaver())
    discovery.set_registry(reg)
    ex = build_distributed_executor(reg, pool=CountingPool(weave_step))
    with pytest.raises(FanoutConfigError):
        await ex.execute(single_step_braid(), name_sets(*[f"o{i}" for i in range(8)]))


# --- cardinality fan-out composes with the distributed executor ---------------
# This is the *other* fan-out: core's one→many entity expansion (ExpandPolicy /
# set_outputs), distinct from this module's batch-across-workers fan-out. It lives
# in LocalExecutor's orchestration, which build_distributed_executor reuses verbatim,
# so it must work unchanged when steps run on workers. (They compose: batch-parallelism
# × cardinality-expansion.) This is the regression guard for that claim.

from braidworks.core.braid import Braid, CapabilityInvocation  # noqa: E402
from braidworks.core.capability import Capability, OutputGroup, WeaverManifest  # noqa: E402
from braidworks.core.executor import ExpandPolicy  # noqa: E402
from braidworks.core.result import WeaveResult, WeaveStatus  # noqa: E402
from braidworks.core.strand import Strand, StrandSet  # noqa: E402
from braidworks.core.weaver import BaseWeaver  # noqa: E402

from fakes import InlinePool  # noqa: E402

ACCESSION = "protein.uniprot.accession"
PATHWAY = "pathway.reactome.id"


class _PathwaysWeaver(BaseWeaver):
    """accession → a *set* of pathway ids (set_outputs) — the one→many fan dimension."""

    def __init__(self) -> None:
        produces = frozenset({PATHWAY})
        cap = Capability(
            id="reactome.pathways",
            consumes=frozenset({ACCESSION}),
            produces=produces,
            output_groups=(OutputGroup(id="g", outputs=produces),),
            backends=("local",),
            set_outputs=produces,
        )
        self._m = WeaverManifest(weaver_id="reactome", version="1.0.0", capabilities=(cap,))

    @property
    def MANIFEST(self):  # type: ignore[override]
        return self._m

    def backend_fingerprint(self, backend):
        return "ds"

    async def execute(self, capability_id, strand_set, *, requested_outputs, backend, params=None):
        acc = strand_set.get(ACCESSION).value
        return WeaveResult(
            capability_id=capability_id,
            weaver_version="1.0.0",
            backend_used=backend,
            computed_groups=frozenset({"g"}),
            status=WeaveStatus.OK,
            strands=(Strand(PATHWAY, [f"R-{acc}-1", f"R-{acc}-2", f"R-{acc}-3"]),),
        )

    async def execute_batch(self, capability_id, strand_sets, *, requested_outputs, backend, params=None):
        return [
            await self.execute(capability_id, ss, requested_outputs=requested_outputs, backend=backend)
            for ss in strand_sets
        ]


def _pathways_braid() -> Braid:
    inv = CapabilityInvocation(
        weaver_id="reactome",
        capability_id="reactome.pathways",
        input_types=frozenset({ACCESSION}),
        output_types=frozenset({PATHWAY}),
        primary_backend="local",
    )
    return Braid(steps=(inv,), from_types=frozenset({ACCESSION}), to_types=frozenset({PATHWAY}))


async def test_cardinality_fanout_through_distributed_executor():
    reg = registry_with(_PathwaysWeaver())
    discovery.set_registry(reg)
    ex = build_distributed_executor(reg, pool=InlinePool(weave_step))
    inputs = [StrandSet.from_strands("e0", [Strand(ACCESSION, "P1")])]
    res = await ex.execute(_pathways_braid(), inputs, expand_policy=ExpandPolicy.all())
    # one protein in → one resolved leaf per pathway, even though the step ran "on a worker".
    assert len(res.resolved) == 3
    assert sorted(leaf.get(PATHWAY).value for leaf in res.resolved) == ["R-P1-1", "R-P1-2", "R-P1-3"]
    assert all(leaf.parent_id == "e0" for leaf in res.resolved)
    assert sorted(leaf.entity_id for leaf in res.resolved) == ["e0#0", "e0#1", "e0#2"]


async def test_cardinality_top_collapses_through_distributed_executor():
    reg = registry_with(_PathwaysWeaver())
    discovery.set_registry(reg)
    ex = build_distributed_executor(reg, pool=InlinePool(weave_step))
    inputs = [StrandSet.from_strands("e0", [Strand(ACCESSION, "P1")])]
    res = await ex.execute(_pathways_braid(), inputs)  # default ExpandPolicy.TOP
    assert len(res.resolved) == 1
    assert res.resolved[0].get(PATHWAY).value == "R-P1-1"  # representative, collapsed in place
