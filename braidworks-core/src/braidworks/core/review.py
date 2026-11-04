"""Explicit human decisions resume only the saved paused branch/phase."""

from dataclasses import dataclass, replace
from typing import Any

from .braid import Braid, CapabilityInvocation
from .executor import ErrorPolicy, ExecutionResult, ExpandPolicy, LocalExecutor, ReviewPolicy
from .query_state import QueryExecutionState
from .result import WeaveStatus
from .strand import MergePolicy, entity_key


@dataclass(frozen=True)
class ReviewDecision:
    entity_key: str
    action: str
    candidate_index: int | None = None

    def __post_init__(self):
        if not isinstance(self.entity_key, str) or not self.entity_key:
            raise ValueError("Review decision requires a stable entity key")
        if self.action not in ("select", "accept", "reject"):
            raise ValueError("Review action expects select, accept or reject")
        if self.action == "select":
            if type(self.candidate_index) is not int or self.candidate_index < 0:
                raise ValueError("select requires a nonnegative candidate index")
        elif self.candidate_index is not None:
            raise ValueError("Only select accepts a candidate index")

    def to_json(self) -> dict[str, Any]:
        return {
            "version": 1,
            "entity_key": self.entity_key,
            "action": self.action,
            "candidate_index": self.candidate_index,
        }

    @classmethod
    def from_json(cls, data):
        if data.get("version") != 1:
            raise ValueError("Unsupported review decision version")
        return cls(data["entity_key"], data["action"], data.get("candidate_index"))


def apply_review_decisions(registry, state, decisions) -> QueryExecutionState:
    """Return a validated copy with explicit continuations; never mutate the caller."""
    state = QueryExecutionState.from_json(state.to_json())
    if not state.done:
        raise ValueError("Finish or resume execution before reviewing its terminal queue")
    seen = set()
    for decision in decisions:
        if not isinstance(decision, ReviewDecision):
            raise TypeError("Review decisions must be ReviewDecision values")
        if decision.entity_key in seen:
            raise ValueError("Duplicate review decision for one entity")
        seen.add(decision.entity_key)
        items = [
            item
            for item in state.result.review_queue
            if entity_key(item.strand_set) == decision.entity_key
        ]
        if len(items) != 1:
            raise ValueError("Review entity is absent or ambiguous; use its saved execution key")
        item = items[0]
        original = item.triggering_result
        context = item.continuation
        if (
            not {"invocation", "kind", "group_index", "traversal_index", "to_types"}
            <= context.keys()
        ):
            raise ValueError("Legacy review lacks phase context; retain it and start a new run")
        if decision.action == "select":
            if original.status is not WeaveStatus.AMBIGUOUS or decision.candidate_index >= len(
                original.candidates
            ):
                raise ValueError("Candidate index does not identify a saved ambiguous candidate")
            chosen = original.candidates[decision.candidate_index]
            approved = replace(
                original,
                status=WeaveStatus.OK,
                strands=chosen.strands,
                candidates=(),
                requires_review=False,
            )
        elif decision.action == "accept":
            if original.status is not WeaveStatus.OK:
                raise ValueError("accept requires an OK result; ambiguous results require select")
            approved = replace(original, requires_review=False)
        else:
            approved = replace(
                original,
                status=WeaveStatus.NO_MATCH,
                strands=(),
                candidates=(),
                requires_review=False,
            )
        ss = item.strand_set
        ss.warnings.append(f"Human review: {decision.action} at {original.capability_id}")
        state.result.review_queue.remove(item)
        state.review_decisions.append(
            {
                "decision": decision.to_json(),
                "observation": original.to_json(),
                "continuation": context,
            }
        )
        if decision.action == "reject":
            state.result.unresolved.append((ss, approved))
            continue
        invocation = CapabilityInvocation.from_json(context["invocation"])
        cap = registry.get_capability(invocation.weaver_id, invocation.capability_id)
        options = state.prepared.request.options
        expansion = ExpandPolicy.all() if context["kind"] == "prelude" else options.expand_policy
        applied, terminal, representative, spawned, errored = ExecutionResult(), set(), {}, [], {}
        executor = LocalExecutor(registry)
        # Reuse deterministic result application. The explicit decision approves this
        # one observation below the confidence floor; subsequent steps keep saved policy.
        executor._apply_result(
            ss,
            approved,
            0,
            invocation,
            cap.set_outputs,
            item.remaining_steps,
            applied,
            terminal,
            representative,
            spawned,
            errored,
            review_policy=ReviewPolicy.ALLOW_CONTINUE,
            error_policy=ErrorPolicy.RECORD_AND_CONTINUE,
            merge_policy=MergePolicy.HIGHEST_CONFIDENCE,
            expand_policy=expansion,
            expand_by_type={},
            confidence_threshold=0,
            expansion_budget=state.budget,
        )
        roots = spawned if entity_key(ss) in terminal else [ss, *spawned]
        braid = Braid(
            item.remaining_steps,
            frozenset().union(*(root.available_types() for root in roots)),
            frozenset(context["to_types"]),
        )
        active = executor.start_state(
            braid,
            roots,
            **{
                **options.executor_kwargs(),
                "expand_policy": expansion,
                "params": state.prepared.effective_params,
                "_expansion_budget": state.budget,
            },
        )
        active.settings["prior_errors"] = {
            entity_key(root): context.get("prior_errors", []) for root in roots
        }
        frame = QueryExecutionState(
            state.prepared,
            state.inputs,
            state.budget,
            applied,
            group_index=context["group_index"],
            traversal_index=context["traversal_index"],
            phase="group",
            current=roots,
            active=active,
            active_kind=context["kind"],
            stop_after_group=True,
        )
        state.review_continuations.append(frame)
    return state
