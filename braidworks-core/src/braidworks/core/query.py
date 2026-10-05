"""Shared query preparation/execution, independent of human interface transports."""

import math
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .braid import BackendPolicy, Braid
from .cache import StrandCache
from .executor import (
    ExecutionResult,
    ExpandMode,
    ExpandPolicy,
    LocalExecutor,
    ReviewPolicy,
    _ExpansionBudget,
)
from .parameters import map_parameter_items, validate_scoped_parameters
from .planner import Braider
from .registry import BraidRegistry
from .strand import StrandSet
from .traverse import resolve_traversal, run_traversed, traversal_route_capabilities


def normalize_expansion(mode: str | None, k: int = 1, *, traversal: bool = False) -> ExpandPolicy:
    """Normalize CLI/browser spellings; omitted traversal expansion means all."""
    if mode is None:
        return ExpandPolicy.all() if traversal else ExpandPolicy.top()
    mode = mode.strip().lower()
    if mode in ("none", "top", "best", "1"):
        return ExpandPolicy.top()
    if mode == "all":
        return ExpandPolicy.all()
    if mode.startswith("top:"):
        try:
            k = int(mode.split(":", 1)[1])
        except ValueError as exc:
            raise ValueError("top:K requires an integer") from exc
        mode = "top_k"
    if mode == "top_k" and type(k) is int:
        return ExpandPolicy.top_k(k)
    raise ValueError("expansion expects top/none, top:K/top_k, or all")


@dataclass(frozen=True)
class QueryOptions:
    backend_policy: BackendPolicy = BackendPolicy.LOCAL_FIRST
    expand_policy: ExpandPolicy = field(default_factory=ExpandPolicy.top)
    review_policy: ReviewPolicy = ReviewPolicy.HALT
    confidence_threshold: float = 0.0
    max_expansion: int = 10_000

    def __post_init__(self):
        if not math.isfinite(self.confidence_threshold) or not 0 <= self.confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be finite and between 0 and 1")
        if type(self.max_expansion) is not int or self.max_expansion < 1:
            raise ValueError("max_expansion must be a positive integer")
        if self.expand_policy.mode is ExpandMode.TOP_K and (
            type(self.expand_policy.k) is not int or self.expand_policy.k < 1
        ):
            raise ValueError("top_k requires a positive integer")

    def to_json(self) -> dict[str, Any]:
        return {
            "backend_policy": self.backend_policy.value,
            "expand": self.expand_policy.mode.value,
            "k": self.expand_policy.k,
            "review_policy": self.review_policy.value,
            "confidence_threshold": self.confidence_threshold,
            "max_expansion": self.max_expansion,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "QueryOptions":
        return cls(
            BackendPolicy(data.get("backend_policy", "local_first")),
            normalize_expansion(data.get("expand", "top"), data.get("k", 1)),
            ReviewPolicy(data.get("review_policy", "halt")),
            data.get("confidence_threshold", 0.0),
            data.get("max_expansion", 10_000),
        )

    def executor_kwargs(self) -> dict[str, Any]:
        return {
            "backend_policy": self.backend_policy,
            "expand_policy": self.expand_policy,
            "review_policy": self.review_policy,
            "confidence_threshold": self.confidence_threshold,
            "max_expansion": self.max_expansion,
        }


@dataclass(frozen=True)
class QueryRequest:
    inputs: tuple[StrandSet, ...]
    targets: frozenset[str]
    traversals: tuple[str, ...] = ()
    params: dict[str, Any] = field(default_factory=dict)
    options: QueryOptions = field(default_factory=QueryOptions)
    parameter_items: tuple[tuple[str | None, str, Any], ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "version": 1,
            "inputs": [ss.to_json() for ss in self.inputs],
            "targets": sorted(self.targets),
            "traversals": list(self.traversals),
            "params": deepcopy(self.params),
            "options": self.options.to_json(),
            "parameter_items": [list(item) for item in self.parameter_items],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "QueryRequest":
        if data.get("version") != 1:
            raise ValueError("Unsupported query request version")
        return cls(
            tuple(StrandSet.from_json(ss) for ss in data["inputs"]),
            frozenset(data["targets"]),
            tuple(data.get("traversals", ())),
            deepcopy(data.get("params", {})),
            QueryOptions.from_json(data.get("options", {})),
            tuple(tuple(item) for item in data.get("parameter_items", ())),
        )


@dataclass(frozen=True)
class PreparedQuery:
    request: QueryRequest
    plans: tuple[tuple[Braid, tuple[int, ...]], ...]
    traversals: tuple[tuple[str, str], ...]
    effective_params: dict[str, dict[str, Any]]
    capability_ids: tuple[tuple[str, str], ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "version": 1,
            "request": self.request.to_json(),
            "plans": [[braid.to_json(), list(indices)] for braid, indices in self.plans],
            "traversals": [list(item) for item in self.traversals],
            "effective_params": deepcopy(self.effective_params),
            "capability_ids": [list(item) for item in self.capability_ids],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "PreparedQuery":
        if data.get("version") != 1:
            raise ValueError("Unsupported prepared query version")
        return cls(
            QueryRequest.from_json(data["request"]),
            tuple((Braid.from_json(braid), tuple(indices)) for braid, indices in data["plans"]),
            tuple(tuple(item) for item in data["traversals"]),
            deepcopy(data["effective_params"]),
            tuple(tuple(item) for item in data["capability_ids"]),
        )


def prepare_query(registry: BraidRegistry, request: QueryRequest) -> PreparedQuery:
    """Copy input state and validate every group/parameter before source I/O."""
    request = QueryRequest.from_json(deepcopy(request.to_json()))
    if not request.targets and not request.traversals:
        raise ValueError("choose outputs or a traversal")
    groups: dict[frozenset[str], list[int]] = {}
    for i, ss in enumerate(request.inputs):
        groups.setdefault(ss.available_types(), []).append(i)
    traversals = tuple(resolve_traversal(registry, token) for token in request.traversals)
    caps = {}
    plans = []
    if traversals:
        caps = traversal_route_capabilities(
            registry,
            list(request.inputs),
            list(traversals),
            request.targets,
            backend_policy=request.options.backend_policy,
        )
    else:
        for types, indices in groups.items():
            braid = Braider(registry).plan(
                types, request.targets, backend_policy=request.options.backend_policy
            )
            plans.append((braid, tuple(indices)))
            caps.update(
                {
                    step.capability_id: registry.get_capability(step.weaver_id, step.capability_id)
                    for step in braid.steps
                }
            )
    if request.params and request.parameter_items:
        raise ValueError("supply params or parameter_items, not both")
    if request.parameter_items:
        supplied = map_parameter_items(list(request.parameter_items), caps)
    elif all(isinstance(value, dict) for value in request.params.values()):
        supplied = validate_scoped_parameters(request.params, caps)
    elif any(isinstance(value, dict) for value in request.params.values()):
        raise ValueError("params must use either bare names or capability mappings, not both")
    else:
        supplied = map_parameter_items(
            [(None, name, value) for name, value in request.params.items()], caps
        )
    effective = {cid: cap.resolve_params(supplied.get(cid)) for cid, cap in caps.items()}
    owners = {
        cap.id: manifest.weaver_id
        for manifest in registry.manifests()
        for cap in manifest.capabilities
    }
    return PreparedQuery(
        request, tuple(plans), traversals, effective, tuple((owners[cid], cid) for cid in caps)
    )


def absorb_result(result: ExecutionResult, part: ExecutionResult) -> None:
    for bucket in ("resolved", "unresolved", "review_queue", "errors", "truncations"):
        getattr(result, bucket).extend(getattr(part, bucket))
    refs = {ref.weaver_id: ref for ref in result.references + part.references}
    result.references = [refs[key] for key in sorted(refs)]


async def execute_query(
    registry: BraidRegistry,
    prepared: PreparedQuery,
    *,
    executor: LocalExecutor | None = None,
    cache: StrandCache | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> ExecutionResult:
    """Compose existing executor/traversal with one global expansion budget."""
    request = prepared.request
    sets = [StrandSet.from_json(deepcopy(ss.to_json())) for ss in request.inputs]
    if executor is not None and cache is not None:
        raise ValueError("supply executor or cache, not both")
    executor = executor if executor is not None else LocalExecutor(registry, cache)
    if on_event:
        on_event({"event": "progress", "input_count": len(sets), "completed_inputs": 0})
    common = {
        **request.options.executor_kwargs(),
        "params": prepared.effective_params,
        "on_event": on_event,
    }
    if prepared.traversals:
        return await run_traversed(
            registry, sets, list(prepared.traversals), request.targets, executor=executor, **common
        )
    result = ExecutionResult()
    budget = _ExpansionBudget(request.options.max_expansion, len(sets))
    completed = 0
    for braid, indices in prepared.plans:
        part = await executor.execute(
            braid, [sets[i] for i in indices], _expansion_budget=budget, **common
        )
        absorb_result(result, part)
        completed += len(indices)
        if on_event:
            on_event({"event": "progress", "input_count": len(sets), "completed_inputs": completed})
    return result
