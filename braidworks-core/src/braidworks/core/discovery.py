"""Discover installed weavers via the ``braidworks.weavers`` entry-point group.

Each weaver package advertises a zero-arg builder under ``braidworks.weavers``
(name = weaver_id, value = ``module:build_callable``). Anything that needs a
registry of "every weaver installed in this environment" — the CLI, an arq worker —
builds it by loading those entry points. A freshly ``pip install``-ed weaver is
picked up with no code change.
"""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import Callable, Iterator

from braidworks.core.registry import BraidRegistry
from braidworks.core.weaver import BaseWeaver

ENTRY_POINT_GROUP = "braidworks.weavers"


def iter_weaver_builders() -> Iterator[tuple[str, Callable[[], BaseWeaver]]]:
    """Yield ``(name, builder)`` for every installed ``braidworks.weavers`` entry point."""
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        yield ep.name, ep.load()


def build_registry_from_entry_points(
    *, only: frozenset[str] | None = None
) -> BraidRegistry:
    """Build a registry from discovered weavers.

    ``only`` restricts to specific entry-point names (weaver ids) — the hook for a
    consumer that should load just a subset (e.g. a worker serving the weavers whose
    data it holds locally).
    """
    registry = BraidRegistry()
    for name, builder in iter_weaver_builders():
        if only is not None and name not in only:
            continue
        registry.register(builder())
    return registry
