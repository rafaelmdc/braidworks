"""How a worker learns which weavers it serves: ``braidworks.weavers`` entry points.

Each weaver package advertises a zero-arg builder under the ``braidworks.weavers``
entry-point group (name = weaver_id, value = ``module:build_callable``). A worker
builds its :class:`~braidworks.core.registry.BraidRegistry` by loading those entry
points and registering whatever they return. A freshly ``pip install``-ed weaver is
servable with no code change here.

The per-process registry is cached (a worker builds it once at startup). Tests — and
workers that should serve only a subset — can override it with :func:`set_registry`
(e.g. to register a fake weaver, or to load only the weavers whose data this worker
actually holds locally).
"""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import Callable, Iterator

from braidworks.core.registry import BraidRegistry
from braidworks.core.weaver import BaseWeaver

ENTRY_POINT_GROUP = "braidworks.weavers"

_registry: BraidRegistry | None = None


def iter_weaver_builders() -> Iterator[tuple[str, Callable[[], BaseWeaver]]]:
    """Yield ``(name, builder)`` for every installed ``braidworks.weavers`` entry point."""
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        yield ep.name, ep.load()


def build_registry_from_entry_points(
    *, only: frozenset[str] | None = None
) -> BraidRegistry:
    """Build a registry from discovered weavers.

    ``only`` restricts to specific entry-point names (weaver ids) — the hook for a
    worker that should serve just the weavers whose data it holds locally.
    """
    registry = BraidRegistry()
    for name, builder in iter_weaver_builders():
        if only is not None and name not in only:
            continue
        registry.register(builder())
    return registry


def set_registry(registry: BraidRegistry | None) -> None:
    """Override (or clear, with ``None``) the cached per-process registry."""
    global _registry
    _registry = registry


def get_registry() -> BraidRegistry:
    """Return the cached registry, building it from entry points on first use."""
    global _registry
    if _registry is None:
        _registry = build_registry_from_entry_points()
    return _registry
