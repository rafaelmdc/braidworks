"""CapabilityInvocation, Braid, BackendPolicy, FallbackCondition.

A ``Braid`` is the serializable plan the braider produces and the executor runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FallbackCondition(Enum):
    """When the executor should retry on the next backend."""

    NO_MATCH = "no_match"
    ERROR = "error"
    BACKEND_UNAVAILABLE = "backend_unavailable"


class BackendPolicy(Enum):
    """How the braider assigns primary and fallback backends per invocation.

    ``ANY`` is deferred until a per-backend cost model exists.
    """

    LOCAL_ONLY = "local_only"
    API_ONLY = "api_only"
    LOCAL_FIRST = "local_first"
    API_FIRST = "api_first"

    @property
    def preference_order(self) -> tuple[str, ...]:
        return {
            BackendPolicy.LOCAL_ONLY: ("local",),
            BackendPolicy.API_ONLY: ("api",),
            BackendPolicy.LOCAL_FIRST: ("local", "api"),
            BackendPolicy.API_FIRST: ("api", "local"),
        }[self]

    @property
    def default_fallback_on(self) -> frozenset[FallbackCondition]:
        if self in (BackendPolicy.LOCAL_FIRST, BackendPolicy.API_FIRST):
            return frozenset(
                {FallbackCondition.NO_MATCH, FallbackCondition.BACKEND_UNAVAILABLE}
            )
        return frozenset()


@dataclass(frozen=True)
class CapabilityInvocation:
    """One step in a braid: a capability call with its backend plan baked in."""

    weaver_id: str
    capability_id: str
    input_types: frozenset[str]
    output_types: frozenset[str]
    primary_backend: str
    fallback_backends: tuple[str, ...] = ()
    fallback_on: frozenset[FallbackCondition] = frozenset()

    def to_json(self) -> dict[str, Any]:
        return {
            "weaver_id": self.weaver_id,
            "capability_id": self.capability_id,
            "input_types": sorted(self.input_types),
            "output_types": sorted(self.output_types),
            "primary_backend": self.primary_backend,
            "fallback_backends": list(self.fallback_backends),
            "fallback_on": [c.value for c in self.fallback_on],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> CapabilityInvocation:
        return cls(
            weaver_id=data["weaver_id"],
            capability_id=data["capability_id"],
            input_types=frozenset(data["input_types"]),
            output_types=frozenset(data["output_types"]),
            primary_backend=data["primary_backend"],
            fallback_backends=tuple(data.get("fallback_backends", [])),
            fallback_on=frozenset(
                FallbackCondition(c) for c in data.get("fallback_on", [])
            ),
        )


@dataclass(frozen=True)
class Braid:
    """An ordered, JSON-serializable plan. The HPC/Celery serialization boundary."""

    steps: tuple[CapabilityInvocation, ...]
    from_types: frozenset[str]
    to_types: frozenset[str]

    def to_json(self) -> dict[str, Any]:
        return {
            "steps": [s.to_json() for s in self.steps],
            "from_types": sorted(self.from_types),
            "to_types": sorted(self.to_types),
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Braid:
        return cls(
            steps=tuple(CapabilityInvocation.from_json(s) for s in data["steps"]),
            from_types=frozenset(data["from_types"]),
            to_types=frozenset(data["to_types"]),
        )
