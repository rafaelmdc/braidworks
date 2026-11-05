"""The shared record→WeaveResult mappers (lookup + resolver).

Every backend of a weaver feeds its records through one of these, so all backends
emit identical strand shapes. They emit exactly the externally-requested outputs
(``capability.outputs_to_compute``) and report ``computed_groups`` as the triggered
groups unioned with the capability's ``always_computed_groups`` (so the cache key
isn't under-reported when a backend computes a group unconditionally). Errors
claim no completed groups; a failed attempt cannot establish output coverage.
"""

from __future__ import annotations

from typing import Any

from braidworks.core.capability import Capability
from braidworks.core.listing import Listing
from braidworks.core.records import Candidate, LookupRecord, MatchStatus, ResolverRecord
from braidworks.core.result import CandidateResult, WeaveResult, WeaveStatus
from braidworks.core.strand import Strand

_RESOLVER_STATUS = {
    MatchStatus.RESOLVED: WeaveStatus.OK,
    MatchStatus.FUZZY_UNIQUE: WeaveStatus.OK,
    MatchStatus.AMBIGUOUS: WeaveStatus.AMBIGUOUS,
    MatchStatus.NO_MATCH: WeaveStatus.NO_MATCH,
    MatchStatus.ERROR: WeaveStatus.ERROR,
}


def _computed_groups(capability: Capability, requested_outputs: frozenset[str]) -> frozenset[str]:
    return capability.triggered_groups(requested_outputs) | capability.always_computed_groups


def _confidence(score: float | None) -> float:
    """Normalize a score to [0, 1] (exact->1.0; 0..1 kept; 0..100 fuzzy scaled)."""
    if score is None:
        return 1.0
    if score <= 1.0:
        return float(score)
    return min(score / 100.0, 1.0)


def _strand(type_id: str, value: Any, capability: Capability, **kwargs: Any) -> Strand:
    """A strand for one produced value, carrying a list's size when known.

    A backend states a partial list by returning a ``Listing``; a plain list under one
    of the capability's declared lists is the whole list. Strands hold plain lists."""
    if isinstance(value, Listing):
        return Strand(type_id, list(value), total=value.total, complete=value.complete, **kwargs)
    if type_id in capability.list_outputs and isinstance(value, list):
        return Strand(type_id, value, total=len(value), **kwargs)
    return Strand(type_id, value, **kwargs)


def _derived_counts(
    strands: list[Strand], capability: Capability, allowed: frozenset[str], **kwargs: Any
) -> list[Strand]:
    """Deprecated ``.count`` aliases: a declared list total, derived from the list's size.

    Omitted when the backend set the count itself or the true size is unknown."""
    by_type = {s.type_id: s for s in strands}
    derived = []
    for list_type, count_type in sorted(capability.totals.items()):
        listed = by_type.get(list_type)
        if (
            count_type in allowed
            and count_type not in by_type
            and listed is not None
            and listed.total is not None
        ):
            derived.append(Strand(count_type, listed.total, **kwargs))
    return derived


def _count_mismatches(strands: list[Strand], capability: Capability) -> tuple[str, ...]:
    """Warn when a backend's own ``.count`` disagrees with its list's known size."""
    by_type = {s.type_id: s for s in strands}
    out = []
    for list_type, count_type in sorted(capability.totals.items()):
        listed, counted = by_type.get(list_type), by_type.get(count_type)
        if listed is None or counted is None or listed.total is None:
            continue
        if counted.value != listed.total:
            out.append(
                f"{count_type} = {counted.value!r} but {list_type} holds {listed.total} "
                "items; the count should be the list's size"
            )
    return tuple(out)


def map_lookup(
    record: LookupRecord,
    *,
    capability: Capability,
    requested_outputs: frozenset[str],
    backend: str,
    weaver_version: str,
    weaver_id: str,
) -> WeaveResult:
    """Map a neutral lookup record to a ``WeaveResult`` for the requested outputs."""
    allowed = capability.outputs_to_compute(requested_outputs)
    provenance = (f"{weaver_id}:{backend}",)

    strands: list[Strand] = []
    errors: tuple[str, ...] = ()
    if record.error is not None:
        status = WeaveStatus.ERROR
        errors = (record.error,)
    elif not record.found:
        status = WeaveStatus.NO_MATCH
    else:
        status = WeaveStatus.OK
        for type_id, value in record.values.items():
            if type_id in allowed and value is not None:
                strands.append(_strand(type_id, value, capability, provenance=provenance))
        strands += _derived_counts(strands, capability, allowed, provenance=provenance)
    mismatches = _count_mismatches(strands, capability)

    return WeaveResult(
        capability_id=capability.id,
        weaver_version=weaver_version,
        backend_used=backend,
        computed_groups=(
            frozenset()
            if status is WeaveStatus.ERROR
            else _computed_groups(capability, requested_outputs)
        ),
        status=status,
        strands=tuple(strands),
        errors=errors,
        warnings=record.warnings + mismatches,
    )


def _candidate_result(
    candidate: Candidate,
    capability: Capability,
    allowed: frozenset[str],
    provenance: tuple[str, ...],
) -> CandidateResult:
    conf = _confidence(candidate.score)
    strands = [
        _strand(t, v, capability, confidence=conf, provenance=provenance)
        for t, v in candidate.values.items()
        if t in allowed and v is not None
    ]
    strands += _derived_counts(strands, capability, allowed, confidence=conf, provenance=provenance)
    return CandidateResult(strands=tuple(strands), confidence=conf)


def map_resolver(
    record: ResolverRecord,
    *,
    capability: Capability,
    requested_outputs: frozenset[str],
    backend: str,
    weaver_version: str,
    weaver_id: str,
) -> WeaveResult:
    """Map a neutral resolver record to a ``WeaveResult`` for the requested outputs."""
    allowed = capability.outputs_to_compute(requested_outputs)
    provenance = (f"{weaver_id}:{backend}",)
    status = _RESOLVER_STATUS[record.status]
    conf = _confidence(record.score)

    strands: list[Strand] = []
    candidates: tuple[CandidateResult, ...] = ()
    errors: tuple[str, ...] = ()
    requires_review = record.requires_review

    if status is WeaveStatus.OK:
        if record.status is MatchStatus.FUZZY_UNIQUE:
            requires_review = True
        for type_id, value in record.values.items():
            if type_id in allowed and value is not None:
                strands.append(
                    _strand(type_id, value, capability, confidence=conf, provenance=provenance)
                )
        strands += _derived_counts(
            strands, capability, allowed, confidence=conf, provenance=provenance
        )
    elif status is WeaveStatus.AMBIGUOUS:
        candidates = tuple(
            _candidate_result(c, capability, allowed, provenance) for c in record.candidates
        )
        requires_review = True
    elif status is WeaveStatus.ERROR:
        errors = (record.error or "backend error",)

    return WeaveResult(
        capability_id=capability.id,
        weaver_version=weaver_version,
        backend_used=backend,
        computed_groups=(
            frozenset()
            if status is WeaveStatus.ERROR
            else _computed_groups(capability, requested_outputs)
        ),
        status=status,
        strands=tuple(strands),
        candidates=candidates,
        errors=errors,
        warnings=_count_mismatches(strands, capability),
        requires_review=requires_review,
    )
