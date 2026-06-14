"""WeaveStepRunner seam: the default is in-process; a custom runner is honored."""

from __future__ import annotations

from braidworks.core import InProcessStepRunner, WeaveStepRunner
from braidworks.core.executor import LocalExecutor
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import WeaveResult
from braidworks.core.strand import Strand, StrandSet

from helpers import (
    ScriptedWeaver,
    name_strand_sets,
    ok_result,
    single_step_braid,
)

ID = "ncbi.taxon.id"


def _taxid_for(ss: StrandSet) -> int:
    return abs(hash(ss.get("organism.name").value)) % 100_000


class RecordingRunner:
    """Wraps another runner and records every call's (weaver_id, backend, size)."""

    def __init__(self, inner: WeaveStepRunner) -> None:
        self._inner = inner
        self.calls: list[tuple[str, str, str, int]] = []

    async def run_step(
        self, weaver_id, capability_id, backend, strand_sets, requested_outputs, **kw
    ) -> list[WeaveResult]:
        self.calls.append((weaver_id, capability_id, backend, len(strand_sets)))
        return await self._inner.run_step(
            weaver_id, capability_id, backend, strand_sets, requested_outputs, **kw
        )


async def test_default_runner_is_in_process_and_unchanged():
    reg = BraidRegistry()
    weaver = ScriptedWeaver(lambda ss, b, r: ok_result(r, Strand(ID, _taxid_for(ss))))
    reg.register(weaver)
    ex = LocalExecutor(reg)  # no runner: defaults to in-process
    res = await ex.execute(single_step_braid({ID}), name_strand_sets("a", "b"))
    assert len(res.resolved) == 2
    assert weaver.batch_calls == 1  # the weaver was actually called in-process


async def test_injected_runner_is_used():
    reg = BraidRegistry()
    weaver = ScriptedWeaver(lambda ss, b, r: ok_result(r, Strand(ID, _taxid_for(ss))))
    reg.register(weaver)
    recorder = RecordingRunner(InProcessStepRunner(reg))
    ex = LocalExecutor(reg, runner=recorder)
    res = await ex.execute(single_step_braid({ID}), name_strand_sets("a", "b", "c"))
    assert len(res.resolved) == 3
    # The seam was exercised: one step, the ncbi weaver, local backend, 3 entities.
    assert recorder.calls == [("ncbi", "ncbi.resolve_name", "local", 3)]


async def test_runner_results_flow_through_without_touching_a_weaver():
    """A runner can fully satisfy a step; the executor never needs the weaver call."""

    class StubRunner:
        async def run_step(
            self, weaver_id, capability_id, backend, strand_sets, requested_outputs, **kw
        ):
            return [
                ok_result(requested_outputs, Strand(ID, 999), backend=backend)
                for _ in strand_sets
            ]

    reg = BraidRegistry()
    weaver = ScriptedWeaver(lambda ss, b, r: ok_result(r, Strand(ID, _taxid_for(ss))))
    reg.register(weaver)
    ex = LocalExecutor(reg, runner=StubRunner())
    res = await ex.execute(single_step_braid({ID}), name_strand_sets("x"))
    assert len(res.resolved) == 1
    assert res.resolved[0].get(ID).value == 999
    assert weaver.batch_calls == 0  # stub answered; the real weaver was never called
