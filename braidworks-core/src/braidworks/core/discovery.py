"""Discover installed weavers via the ``braidworks.weavers`` entry-point group.

Each weaver package advertises a zero-arg builder under ``braidworks.weavers``
(name = weaver_id, value = ``module:build_callable``). Anything that needs a
registry of "every weaver installed in this environment" — the CLI, an arq worker —
builds it by loading those entry points. A freshly ``pip install``-ed weaver is
picked up with no code change.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from importlib.metadata import EntryPoint, entry_points

from braidworks.core.registry import BraidRegistry
from braidworks.core.weaver import BaseWeaver

ENTRY_POINT_GROUP = "braidworks.weavers"


class DiscoveryPolicy(StrEnum):
    """Whether a broken selected plugin aborts discovery or appears in the report."""

    STRICT = "strict"
    TOLERANT = "tolerant"


@dataclass(frozen=True)
class DiscoveryFailure:
    """Serializable diagnostic; does not retain the plugin exception or traceback."""

    name: str
    value: str
    stage: str
    exception_type: str
    message: str

    def to_json(self) -> dict:
        return {
            "version": 1,
            "name": self.name,
            "value": self.value,
            "stage": self.stage,
            "exception_type": self.exception_type,
            "message": self.message,
        }

    @classmethod
    def from_json(cls, data: dict) -> DiscoveryFailure:
        fields = ("name", "value", "stage", "exception_type", "message")
        if data.get("version") != 1 or any(not isinstance(data.get(key), str) for key in fields):
            raise ValueError("Invalid discovery failure JSON")
        if data["stage"] not in ("load", "build", "register"):
            raise ValueError("Invalid discovery failure stage")
        return cls(**{key: data[key] for key in fields})


class DiscoveryReport:
    """Runtime registry and immutable diagnostics; live weavers are not serialized."""

    def __init__(self, registry: BraidRegistry, failures: tuple[DiscoveryFailure, ...]) -> None:
        self.registry = registry
        self.failures = failures


def _selected_entry_points(only: frozenset[str] | None) -> Iterator[EntryPoint]:
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        if only is None or ep.name in only:
            yield ep


def iter_weaver_builders(
    *,
    only: frozenset[str] | None = None,
) -> Iterator[tuple[str, Callable[[], BaseWeaver]]]:
    """Yield installed builders, filtering metadata before importing plugins."""
    for ep in _selected_entry_points(only):
        yield ep.name, ep.load()


def discover_registry(
    *,
    only: frozenset[str] | None = None,
    policy: DiscoveryPolicy = DiscoveryPolicy.STRICT,
) -> DiscoveryReport:
    """Build a fresh registry with explicit per-plugin failure policy.

    Filtering uses entry-point names before any import. Strict failures propagate
    unchanged, with a diagnostic exception note. Tolerant discovery skips failing
    plugins and records their load/build/register stage. Metadata enumeration failures
    and process-control exceptions propagate in both modes.
    """
    policy = DiscoveryPolicy(policy)
    registry = BraidRegistry()
    failures = []
    for ep in _selected_entry_points(only):
        stage = "load"
        try:
            builder = ep.load()
            stage = "build"
            weaver = builder()
            stage = "register"
            registry.register(weaver)
        except Exception as exc:
            if policy is DiscoveryPolicy.STRICT:
                exc.add_note(
                    f"Weaver discovery: {ep.name} ({getattr(ep, 'value', '')}), stage={stage}"
                )
                raise
            failures.append(
                DiscoveryFailure(
                    name=ep.name,
                    value=getattr(ep, "value", ""),
                    stage=stage,
                    exception_type=type(exc).__name__,
                    message=str(exc),
                )
            )
    return DiscoveryReport(registry, tuple(failures))


def build_registry_from_entry_points(*, only: frozenset[str] | None = None) -> BraidRegistry:
    """Compatibility wrapper: strictly build a fresh registry of selected weavers."""
    return discover_registry(only=only, policy=DiscoveryPolicy.STRICT).registry
