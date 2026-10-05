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
from braidworks.core.executor import ExecutionError, LocalExecutor, ReviewPolicy, ReviewQueueItem
from braidworks.core.parameters import map_parameter_items, validate_scoped_parameters
from braidworks.core.planner import Braider
from braidworks.core.references import Reference
from braidworks.core.strand import Strand, StrandSet

if TYPE_CHECKING:
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
    review_queue retains paused candidates; review_required includes IDs whose
    automatic selections still need curation. Paused IDs also count as unresolved
    for the coverage mask.
    ``unresolved`` lists every input id that produced *none* of the requested types
    (never routed, empty source, or errored) — the ids a coverage mask marks absent.
    """

    resolved: dict[str, dict[str, Any]] = field(default_factory=dict)
    unresolved: list[str] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    errors: list[ExecutionError] = field(default_factory=list)
    review_queue: list[ReviewQueueItem] = field(default_factory=list)
    review_required: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        """Serialize values, coverage, source references and error diagnostics."""
        return {
            "resolved": self.resolved,
            "unresolved": list(self.unresolved),
            "references": [reference.to_json() for reference in self.references],
            "errors": [error.to_json() for error in self.errors],
            "review_queue": [item.to_json() for item in self.review_queue],
            "review_required": list(self.review_required),
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> FetchResult:
        return cls(
            resolved={key: dict(values) for key, values in data.get("resolved", {}).items()},
            unresolved=list(data.get("unresolved", [])),
            references=[Reference.from_json(reference) for reference in data.get("references", [])],
            errors=[ExecutionError.from_json(error) for error in data.get("errors", [])],
            review_queue=[ReviewQueueItem.from_json(item) for item in data.get("review_queue", [])],
            review_required=list(data.get("review_required", [])),
        )

    def get(self, id_: str) -> dict[str, Any]:
        """Values produced for one id (empty dict if it did not resolve)."""
        return self.resolved.get(id_, {})

    def column(self, want_type: str) -> dict[str, Any]:
        """The ``{id: value}`` map for a single ``want`` type across all resolved ids.

        Convenience for the common "I asked for one attribute, give me the column"
        case, e.g. ``fetch("microbe.metabolism.reactions", ids).column(...)``.
        """
        return {
            id_: values[want_type] for id_, values in self.resolved.items() if want_type in values
        }


def _as_list(want: str | list[str]) -> list[str]:
    return [want] if isinstance(want, str) else list(want)


def _resolve_params(
    params: dict[str, Any] | None, braid: Any, registry: BraidRegistry
) -> dict[str, dict[str, Any]] | None:
    """Normalize ``params`` into the executor's ``{capability_id: {name: value}}`` shape.

    Two accepted forms, disambiguated by shape:

    * **native** — already ``{capability_id: {name: value}}`` (every value is a dict):
      scopes and values are validated before I/O, for callers targeting one capability.
    * **bare** — ``{name: value}`` (scalar values): each name is mapped onto *every*
      capability in the planned route that declares a parameter of that name, mirroring
      the CLI's bare ``--param NAME=VALUE`` behaviour. This is the friendly default
      (e.g. ``params={"organism": "9606"}``).
    """
    if not params:
        return None
    caps_by_id = {
        s.capability_id: registry.get_capability(s.weaver_id, s.capability_id) for s in braid.steps
    }
    if all(isinstance(v, dict) for v in params.values()):
        return validate_scoped_parameters(params, caps_by_id)
    if any(isinstance(v, dict) for v in params.values()):
        raise ValueError("params must use either bare names or capability mappings, not both")
    return map_parameter_items([(None, name, value) for name, value in params.items()], caps_by_id)


async def async_fetch(
    want: str | list[str],
    ids: list[str],
    *,
    have: str = DEFAULT_HAVE,
    params: dict[str, Any] | None = None,
    registry: BraidRegistry | None = None,
    only: frozenset[str] | None = None,
    review_policy: ReviewPolicy = ReviewPolicy.HALT,
    confidence_threshold: float = 0.0,
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
        review_policy: HALT preserves ambiguous candidates in review_queue by default.
            ALLOW_CONTINUE explicitly opts into representative selection.
        confidence_threshold: Minimum confidence, between 0 and 1; lower results pause.

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
        braid,
        strand_sets,
        params=_resolve_params(params, braid, reg),
        review_policy=review_policy,
        confidence_threshold=confidence_threshold,
    )

    out = FetchResult(
        references=list(result.references),
        errors=list(result.errors),
        review_queue=list(result.review_queue),
        review_required=list(
            dict.fromkeys(
                [item.strand_set.entity_id for item in result.review_queue]
                + [ss.entity_id for ss in result.resolved if ss.requires_review]
            )
        ),
    )
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
    review_policy: ReviewPolicy = ReviewPolicy.HALT,
    confidence_threshold: float = 0.0,
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
            want,
            ids,
            have=have,
            params=params,
            registry=registry,
            only=only,
            review_policy=review_policy,
            confidence_threshold=confidence_threshold,
        )
    )
