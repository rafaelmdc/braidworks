"""One serializable orchestration cursor for heterogeneous routes and traversal phases."""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .exceptions import NoPathError, NoPlanError
from .execution_state import ExecutionState
from .executor import ExecutionResult, ExpandPolicy, LocalExecutor, _ExpansionBudget
from .planner import Braider
from .query import PreparedQuery, absorb_result
from .strand import StrandSet
from .traverse import _absorb_dead_ends


@dataclass
class QueryExecutionState:
    prepared: PreparedQuery
    inputs: list[StrandSet]
    budget: _ExpansionBudget
    result: ExecutionResult = field(default_factory=ExecutionResult)
    group_index: int = 0
    traversal_index: int = 0
    phase: str = "group"
    current: list[StrandSet] = field(default_factory=list)
    active: ExecutionState | None = None
    active_kind: str | None = None
    settings_override: dict[str, Any] = field(default_factory=dict)
    stop_after_group: bool = False
    review_continuations: list["QueryExecutionState"] = field(default_factory=list)
    review_decisions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def done(self) -> bool:
        return self.phase == "done" and not self.review_continuations

    def to_json(self) -> dict[str, Any]:
        return deepcopy(
            {
                "version": 2,
                "prepared": self.prepared.to_json(),
                "inputs": [ss.to_json() for ss in self.inputs],
                "budget": {
                    "limit": self.budget.limit,
                    "leaves": self.budget.leaves,
                    "next_identity": self.budget.next_identity,
                },
                "result": self.result.to_json(),
                "group_index": self.group_index,
                "traversal_index": self.traversal_index,
                "phase": self.phase,
                "current": [ss.to_json() for ss in self.current],
                "active": self.active.to_json() if self.active else None,
                "active_kind": self.active_kind,
                "settings_override": self.settings_override,
                "stop_after_group": self.stop_after_group,
                "review_continuations": [frame.to_json() for frame in self.review_continuations],
                "review_decisions": self.review_decisions,
            }
        )

    @classmethod
    def from_json(cls, data: dict[str, Any], *, _budget=None) -> "QueryExecutionState":
        if data.get("version") not in (1, 2):
            raise ValueError("Unsupported query execution state version")
        budget = _budget if _budget is not None else _ExpansionBudget(**data["budget"])
        if _budget is not None and data["budget"] != {
            "limit": budget.limit,
            "leaves": budget.leaves,
            "next_identity": budget.next_identity,
        }:
            raise ValueError("Conflicting review continuation expansion budget")
        state = cls(
            PreparedQuery.from_json(data["prepared"]),
            [StrandSet.from_json(ss) for ss in data["inputs"]],
            budget,
            ExecutionResult.from_json(data["result"]),
            data["group_index"],
            data["traversal_index"],
            data["phase"],
            [StrandSet.from_json(ss) for ss in data["current"]],
            ExecutionState.from_json(data["active"], _budget=budget) if data["active"] else None,
            data["active_kind"],
            deepcopy(data["settings_override"]),
            data.get("stop_after_group", False),
            [
                cls.from_json(frame, _budget=budget)
                for frame in data.get("review_continuations", [])
            ],
            deepcopy(data.get("review_decisions", [])),
        )
        if state.phase not in ("group", "prelude", "fan", "targets", "done"):
            raise ValueError("Invalid query execution phase")
        count = len({ss.available_types() for ss in state.prepared.request.inputs})
        if (
            type(state.group_index) is not int
            or not 0 <= state.group_index <= count
            or type(state.traversal_index) is not int
            or not 0 <= state.traversal_index <= len(state.prepared.traversals)
        ):
            raise ValueError("Invalid query phase cursor")
        if state.active is not None and state.active_kind not in (
            "route",
            "prelude",
            "fan",
            "targets",
        ):
            raise ValueError("Invalid active query phase")
        return state


def start_query(prepared: PreparedQuery, *, budget=None) -> QueryExecutionState:
    inputs = [StrandSet.from_json(deepcopy(ss.to_json())) for ss in prepared.request.inputs]
    budget = (
        budget
        if budget is not None
        else _ExpansionBudget(prepared.request.options.max_expansion, len(inputs))
    )
    for ss in inputs:
        ss.execution_key = None  # Every new query owns distinct internal row identities.
        budget.identify(ss)
    return QueryExecutionState(prepared, inputs, budget)


async def continue_query(
    registry,
    state: QueryExecutionState,
    *,
    executor=None,
    cache=None,
    on_event=None,
    on_checkpoint=None,
) -> ExecutionResult:
    """Continue saved waves/phases without restarting completed groups or traversals."""
    if executor is not None and cache is not None:
        raise ValueError("supply executor or cache, not both")
    executor = executor if executor is not None else LocalExecutor(registry, cache)
    request = state.prepared.request
    groups = {}
    for i, ss in enumerate(state.prepared.request.inputs):
        groups.setdefault(ss.available_types(), []).append(i)
    group_indices = list(groups.values())
    options = {
        **request.options.executor_kwargs(),
        "params": state.prepared.effective_params,
        "_expansion_budget": state.budget,
    }
    # Overrides are only the legacy lower-level error/merge contracts.
    if state.settings_override:
        from .executor import ErrorPolicy
        from .strand import MergePolicy

        options.update(
            error_policy=ErrorPolicy(state.settings_override["error_policy"]),
            merge_policy=MergePolicy(state.settings_override["merge_policy"]),
        )

    def checkpoint():
        if on_checkpoint:
            on_checkpoint(state)

    def finish_group():
        state.group_index += 1
        state.traversal_index = 0
        state.phase = "done" if state.stop_after_group else "group"
        state.current = []
        if on_event:
            on_event(
                {
                    "event": "progress",
                    "input_count": len(state.inputs),
                    "completed_inputs": sum(
                        len(indices) for indices in group_indices[: state.group_index]
                    ),
                }
            )
        checkpoint()

    checkpoint()
    while state.review_continuations:
        frame = state.review_continuations[0]
        await continue_query(
            registry,
            frame,
            executor=executor,
            on_event=on_event,
            on_checkpoint=lambda _: checkpoint(),
        )
        absorb_result(state.result, frame.result)
        state.review_continuations.pop(0)
        checkpoint()
    while not state.done:
        if state.active is not None:
            result = await executor.continue_state(
                state.active, on_event=on_event, on_checkpoint=lambda _: checkpoint()
            )
            kind = state.active_kind
            for item in result.review_queue:
                item.continuation.update(
                    group_index=state.group_index, traversal_index=state.traversal_index, kind=kind
                )
            state.active = None
            state.active_kind = None
            if kind in ("route", "targets"):
                absorb_result(state.result, result)
                finish_group()
            else:
                _absorb_dead_ends(state.result, result)
                if kind == "prelude":
                    wid, cid = state.prepared.traversals[state.traversal_index]
                    source = registry.get_capability(wid, cid).consumes
                    state.current = [ss.restricted_to(source) for ss in result.resolved]
                    state.phase = "fan"
                else:
                    state.current = result.resolved
                    state.traversal_index += 1
                    state.phase = (
                        "prelude"
                        if state.traversal_index < len(state.prepared.traversals)
                        else "targets"
                    )
                checkpoint()
            continue
        if state.phase == "group":
            if state.group_index >= len(group_indices):
                state.phase = "done"
                checkpoint()
                break
            state.current = [state.inputs[i] for i in group_indices[state.group_index]]
            if not state.prepared.traversals:
                braid = state.prepared.plans[state.group_index][0]
                state.active = executor.start_state(braid, state.current, **options)
                state.active_kind = "route"
                checkpoint()
            else:
                state.phase = "prelude"
                checkpoint()
        elif not state.current:
            finish_group()
        elif state.phase == "prelude":
            wid, cid = state.prepared.traversals[state.traversal_index]
            source = registry.get_capability(wid, cid).consumes
            available = frozenset().union(*(ss.available_types() for ss in state.current))
            prelude = None
            if not source <= available:
                try:
                    prelude = Braider(registry).plan(
                        available, source, backend_policy=request.options.backend_policy
                    )
                except (NoPathError, NoPlanError):
                    pass  # Fan preflight retains the precise missing-input diagnostic.
            if prelude is not None and prelude.steps:
                state.active = executor.start_state(
                    prelude, state.current, **{**options, "expand_policy": ExpandPolicy.all()}
                )
                state.active_kind = "prelude"
            else:
                state.phase = "fan"
            checkpoint()
        elif state.phase == "fan":
            wid, cid = state.prepared.traversals[state.traversal_index]
            source = registry.get_capability(wid, cid).consumes
            state.current = [ss.restricted_to(source) for ss in state.current]
            braid = Braider(registry).plan_capability(
                wid, cid, backend_policy=request.options.backend_policy
            )
            state.active = executor.start_state(braid, state.current, **options)
            state.active_kind = "fan"
            checkpoint()
        elif state.phase == "targets":
            if request.targets:
                available = frozenset().union(*(ss.available_types() for ss in state.current))
                braid = Braider(registry).plan(
                    available, request.targets, backend_policy=request.options.backend_policy
                )
                state.active = executor.start_state(braid, state.current, **options)
                state.active_kind = "targets"
                checkpoint()
            else:
                state.result.resolved.extend(state.current)
                finish_group()
    return state.result
