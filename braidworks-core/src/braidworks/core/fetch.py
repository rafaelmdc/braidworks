"""``fetch`` — the one-call convenience facade over discover → plan → execute.

The full braid flow is four steps: build a registry of weavers, plan a route from
the types you *have* to the types you *want*, execute it over a batch of inputs, and
dig the values out of the resolved ``StrandSet``s. That is the right amount of
control for the executor and the CLI, but a caller who just wants "give me attribute
Y for these N ids" should not have to assemble it by hand.

``fetch`` collapses those four steps into one batch call and hands back a plain,
per-id structure — plus the crucial datum that a raw executor run makes you compute
yourself: **which ids came back empty**. That distinction (resolved vs. unresolved)
is exactly what a caller building a coverage mask needs.

This is a *thin, additive facade*: it composes the existing public pieces
(:func:`build_registry_from_entry_points`, :class:`Braider`, :class:`LocalExecutor`)
with friendly defaults and adds **zero** source-specific knowledge. New weavers work
through it automatically via entry-point discovery; it never imports a weaver. For
anything past a straight batch lookup (custom policies, traversal fan-out, streaming
events), drop down to ``Braider``/``LocalExecutor`` directly — ``fetch`` is the easy
80%, not a replacement.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from braidworks.core.discovery import build_registry_from_entry_points
from braidworks.core.executor import LocalExecutor
from braidworks.core.planner import Braider
from braidworks.core.strand import Strand, StrandSet

if TYPE_CHECKING:
    from braidworks.core.executor import ExecutionError
    from braidworks.core.references import Reference
    from braidworks.core.registry import BraidRegistry

# The main organism join key — the type most lookups start from, so it is the
# default ``have`` and callers usually pass only ``want`` and ``ids``.
DEFAULT_HAVE = "ncbi.taxon.id"


@dataclass
class FetchResult:
    """The outcome of one :func:`fetch` call, keyed by input id.

    ``resolved`` maps each id that produced at least one requested value to a dict of
    ``{want_type: value}`` (only the ``want`` types that were actually produced
    appear — a partially-resolved id is in ``resolved`` with the subset it reached).
    ``unresolved`` lists every input id that produced *none* of the requested types
    (never routed, empty source, or errored) — the ids a coverage mask marks absent.
    """

    resolved: dict[str, dict[str, Any]] = field(default_factory=dict)
    unresolved: list[str] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    errors: list[ExecutionError] = field(default_factory=list)

    def get(self, id_: str) -> dict[str, Any]:
        """Values produced for one id (empty dict if it did not resolve)."""
        return self.resolved.get(id_, {})

    def column(self, want_type: str) -> dict[str, Any]:
        """The ``{id: value}`` map for a single ``want`` type across all resolved ids.

        Convenience for the common "I asked for one attribute, give me the column"
        case, e.g. ``fetch("microbe.metabolism.reactions", ids).column(...)``.
        """
        return {
            id_: values[want_type]
            for id_, values in self.resolved.items()
            if want_type in values
        }


def _as_list(want: str | list[str]) -> list[str]:
    return [want] if isinstance(want, str) else list(want)


def _resolve_params(
    params: dict[str, Any] | None, braid: Any, registry: BraidRegistry
) -> dict[str, dict[str, Any]] | None:
    """Normalize ``params`` into the executor's ``{capability_id: {name: value}}`` shape.

    Two accepted forms, disambiguated by shape:

    * **native** — already ``{capability_id: {name: value}}`` (every value is a dict):
      passed through unchanged, for callers who want to target one capability.
    * **bare** — ``{name: value}`` (scalar values): each name is mapped onto *every*
      capability in the planned route that declares a parameter of that name, mirroring
      the CLI's bare ``--param NAME=VALUE`` behaviour. This is the friendly default
      (e.g. ``params={"organism": "9606"}``).
    """
    if not params:
        return None
    if all(isinstance(v, dict) for v in params.values()):
        return params  # already native per-capability form
    caps_by_id = {
        s.capability_id: registry.get_capability(s.weaver_id, s.capability_id)
        for s in braid.steps
    }
    mapped: dict[str, dict[str, Any]] = {}
    for name, value in params.items():
        for cid, cap in caps_by_id.items():
            if any(p.name == name for p in cap.parameters):
                mapped.setdefault(cid, {})[name] = value
    return mapped


async def async_fetch(
    want: str | list[str],
    ids: list[str],
    *,
    have: str = DEFAULT_HAVE,
    params: dict[str, Any] | None = None,
    registry: BraidRegistry | None = None,
    only: frozenset[str] | None = None,
) -> FetchResult:
    """Batch-resolve ``want`` for ``ids`` of type ``have``. Async form of :func:`fetch`.

    Use this when you are already inside an event loop; otherwise call :func:`fetch`.

    Args:
        want: One target strand type, or several (e.g. ``"microbe.metabolism.reactions"``
            or ``["microbe.trait.gram_stain", "microbe.trait.motility"]``).
        ids: The values you have, all of type ``have`` (e.g. NCBI taxids as strings).
            Duplicates collapse; order is not significant.
        have: The input strand type. Defaults to ``ncbi.taxon.id``.
        params: Capability parameters — bare ``{name: value}`` (mapped onto every
            declaring step) or native ``{capability_id: {name: value}}``.
        registry: A prebuilt registry to reuse across many calls (skips re-discovery,
            which matters when fetching many attributes). Defaults to entry-point
            discovery.
        only: When discovering, restrict to these weaver ids.

    Returns:
        A :class:`FetchResult` bucketing every input id into ``resolved`` / ``unresolved``.
    """
    want_types = _as_list(want)
    reg = registry if registry is not None else build_registry_from_entry_points(only=only)

    braid = Braider(reg).plan(
        available_types=frozenset({have}),
        target_types=frozenset(want_types),
    )
    strand_sets = [StrandSet.from_strands(i, [Strand(have, i)]) for i in dict.fromkeys(ids)]
    result = await LocalExecutor(reg).execute(
        braid, strand_sets, params=_resolve_params(params, braid, reg)
    )

    out = FetchResult(references=list(result.references), errors=list(result.errors))
    seen: set[str] = set()
    for ss in result.resolved:
        values = {t: ss.get(t).value for t in want_types if ss.get(t) is not None}
        if values:
            out.resolved[ss.entity_id] = values
            seen.add(ss.entity_id)
    # Everything we were asked for that did not produce a requested value is absent —
    # unresolved bucket, empty resolves, review, errors, or an id that never returned.
    out.unresolved = [i for i in dict.fromkeys(ids) if i not in seen]
    return out


def fetch(
    want: str | list[str],
    ids: list[str],
    *,
    have: str = DEFAULT_HAVE,
    params: dict[str, Any] | None = None,
    registry: BraidRegistry | None = None,
    only: frozenset[str] | None = None,
) -> FetchResult:
    """Batch-resolve ``want`` for ``ids`` of type ``have`` — the one-call data path.

    Synchronous wrapper over :func:`async_fetch` (runs its own event loop via
    ``asyncio.run``). Call :func:`async_fetch` instead if you are already inside a
    running loop. See :func:`async_fetch` for the full argument reference.

    Example::

        from braidworks import fetch

        res = fetch("microbe.metabolism.reactions", ids=["853", "1680"])
        res.get("853")["microbe.metabolism.reactions"]   # -> [ {abbreviation: …}, … ]
        res.unresolved                                    # -> ids with no AGORA2 model
    """
    return asyncio.run(
        async_fetch(
            want, ids, have=have, params=params, registry=registry, only=only
        )
    )
