"""The shared record→WeaveResult mappers (lookup + resolver).

Every backend of a weaver feeds its records through one of these, so all backends
emit identical strand shapes. They emit exactly the externally-requested outputs
(``capability.outputs_to_compute``) and report ``computed_groups`` as the triggered
groups unioned with the capability's ``always_computed_groups`` (so the cache key
isn't under-reported when a backend computes a group unconditionally).
"""

from __future__ import annotations

from braidworks.core.capability import Capability
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
                strands.append(Strand(type_id, value, provenance=provenance))

    return WeaveResult(
        capability_id=capability.id,
        weaver_version=weaver_version,
        backend_used=backend,
        computed_groups=_computed_groups(capability, requested_outputs),
        status=status,
        strands=tuple(strands),
        errors=errors,
    )


def _candidate_result(
    candidate: Candidate, allowed: frozenset[str], provenance: tuple[str, ...]
) -> CandidateResult:
    conf = _confidence(candidate.score)
    strands = tuple(
        Strand(t, v, confidence=conf, provenance=provenance)
        for t, v in candidate.values.items()
        if t in allowed and v is not None
    )
    return CandidateResult(strands=strands, confidence=conf)


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
                strands.append(Strand(type_id, value, confidence=conf, provenance=provenance))
    elif status is WeaveStatus.AMBIGUOUS:
        candidates = tuple(_candidate_result(c, allowed, provenance) for c in record.candidates)
        requires_review = True
    elif status is WeaveStatus.ERROR:
        errors = (record.error or "backend error",)

    return WeaveResult(
        capability_id=capability.id,
        weaver_version=weaver_version,
        backend_used=backend,
        computed_groups=_computed_groups(capability, requested_outputs),
        status=status,
        strands=tuple(strands),
        candidates=candidates,
        errors=errors,
        requires_review=requires_review,
    )
