"""Serializable executor memento: applied waves, chunk cursor and reroute state.

Runtime registry/cache/runner/callback handles are deliberately absent. Snapshots
capture values after deterministic application, never pre-application progress.
"""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .braid import Braid
from .executor import ExecutionResult, _ExpansionBudget
from .result import WeaveResult
from .strand import StrandSet


@dataclass
class ExecutionState:
    braid: Braid
    inputs: list[StrandSet]
    settings: dict[str, Any]
    budget: _ExpansionBudget
    result: ExecutionResult = field(default_factory=ExecutionResult)
    initialized: bool = False
    survivors: list[StrandSet] = field(default_factory=list)
    chunk_start: int = 0
    chunk_active: bool = False
    wave_index: int = 0
    live: list[StrandSet] = field(default_factory=list)
    terminal: set[str] = field(default_factory=set)
    representative: dict[str, WeaveResult] = field(default_factory=dict)
    errored: dict[str, set[tuple[str, str]]] = field(default_factory=dict)
    reroute_candidates: list[tuple[StrandSet, frozenset[tuple[str, str]]]] = field(
        default_factory=list
    )
    reroute_index: int = 0
    reroute_state: "ExecutionState | None" = None
    stage: str = "chunks"
    in_wave: bool = False

    @property
    def done(self) -> bool:
        return self.stage == "done"

    def _entities(self):
        for ss in self.inputs + self.survivors + self.live:
            yield ss
        for bucket in self.result._entity_buckets().values():
            yield from bucket
        for ss, _ in self.reroute_candidates:
            yield ss
        if self.reroute_state is not None:
            yield from self.reroute_state._entities()

    def to_json(self) -> dict[str, Any]:
        if self.in_wave:
            raise ValueError("Cannot snapshot an unapplied wave; load the last checkpoint")
        entities = {}
        for ss in self._entities():
            if ss.execution_key is None:
                raise ValueError("Execution snapshots require stable entity keys")
            entities[ss.execution_key] = ss.to_json()
        return deepcopy(
            {
                "version": 1,
                "braid": self.braid.to_json(),
                "settings": self.settings,
                "entities": entities,
                "inputs": [ss.execution_key for ss in self.inputs],
                "survivors": [ss.execution_key for ss in self.survivors],
                "live": [ss.execution_key for ss in self.live],
                "budget": {
                    "limit": self.budget.limit,
                    "leaves": self.budget.leaves,
                    "next_identity": self.budget.next_identity,
                },
                "result": self.result.to_json(),
                "initialized": self.initialized,
                "chunk_start": self.chunk_start,
                "chunk_active": self.chunk_active,
                "wave_index": self.wave_index,
                "terminal": sorted(self.terminal),
                "representative": {
                    key: value.to_json() for key, value in self.representative.items()
                },
                "errored": {
                    key: [list(item) for item in sorted(values)]
                    for key, values in self.errored.items()
                },
                "reroute_candidates": [
                    [ss.execution_key, [list(item) for item in sorted(failed)]]
                    for ss, failed in self.reroute_candidates
                ],
                "reroute_index": self.reroute_index,
                "reroute_state": self.reroute_state.to_json() if self.reroute_state else None,
                "stage": self.stage,
            }
        )

    @classmethod
    def from_json(cls, data: dict[str, Any], *, _entities=None, _budget=None) -> "ExecutionState":
        if data.get("version") != 1:
            raise ValueError("Unsupported execution state version")
        entities = (
            _entities
            if _entities is not None
            else {key: StrandSet.from_json(value) for key, value in data["entities"].items()}
        )
        if any(ss.execution_key != key for key, ss in entities.items()):
            raise ValueError("Conflicting execution entity keys")
        budget = _budget if _budget is not None else _ExpansionBudget(**data["budget"])
        result = ExecutionResult.from_json(data["result"])
        result.resolved = [entities[ss.execution_key] for ss in result.resolved]
        result.unresolved = [(entities[ss.execution_key], wr) for ss, wr in result.unresolved]
        for item in result.review_queue + result.errors:
            item.strand_set = entities[item.strand_set.execution_key]
        state = cls(
            Braid.from_json(data["braid"]),
            [entities[key] for key in data["inputs"]],
            deepcopy(data["settings"]),
            budget,
            result,
            data["initialized"],
            [entities[key] for key in data["survivors"]],
            data["chunk_start"],
            data["chunk_active"],
            data["wave_index"],
            [entities[key] for key in data["live"]],
            set(data["terminal"]),
            {key: WeaveResult.from_json(value) for key, value in data["representative"].items()},
            {key: {tuple(item) for item in values} for key, values in data["errored"].items()},
            [
                (entities[key], frozenset(tuple(item) for item in failed))
                for key, failed in data["reroute_candidates"]
            ],
            data["reroute_index"],
            None,
            data["stage"],
        )
        if state.stage not in ("chunks", "reroute", "done"):
            raise ValueError("Invalid execution stage")
        if any(
            type(value) is not int or value < 0
            for value in (state.chunk_start, state.wave_index, state.reroute_index)
        ):
            raise ValueError("Invalid execution cursor")
        if (
            state.chunk_start > len(state.survivors)
            or state.wave_index > len(state.braid.waves())
            or state.reroute_index > len(state.reroute_candidates)
        ):
            raise ValueError("Execution cursor exceeds its phase")
        if data.get("reroute_state") is not None:
            state.reroute_state = cls.from_json(
                data["reroute_state"], _entities=entities, _budget=budget
            )
        return state
