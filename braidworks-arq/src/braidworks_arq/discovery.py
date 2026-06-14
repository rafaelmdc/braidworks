"""How a worker learns which weavers it serves: ``braidworks.weavers`` entry points.

The discovery primitives now live in :mod:`braidworks.core.discovery` (shared with
the ``braidworks`` CLI); this module keeps the worker-local **cached registry**
(``get_registry`` / ``set_registry``) and re-exports the builders for back-compat.

The per-process registry is cached (a worker builds it once at startup). Tests — and
workers that should serve only a subset — can override it with :func:`set_registry`
(e.g. to register a fake weaver, or to load only the weavers whose data this worker
actually holds locally, via ``build_registry_from_entry_points(only=...)``).
"""

from __future__ import annotations

from braidworks.core.discovery import (
    ENTRY_POINT_GROUP,
    build_registry_from_entry_points,
    iter_weaver_builders,
)
from braidworks.core.registry import BraidRegistry

__all__ = [
    "ENTRY_POINT_GROUP",
    "iter_weaver_builders",
    "build_registry_from_entry_points",
    "set_registry",
    "get_registry",
]

_registry: BraidRegistry | None = None


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
