"""The single ``TaxonMatch -> WeaveResult`` mapper.

Both backends feed their results through this one function, which is what
guarantees ``local`` and ``api`` emit identical strand shapes. It emits exactly
the externally-requested outputs (``capability.outputs_to_compute``) and reports
``computed_groups`` as everything actually computed (core is always computed
internally, even when only lineage was requested).
"""

from __future__ import annotations

from braidworks.core import CandidateResult, Capability, Strand, WeaveResult, WeaveStatus

from . import vocab
from .intermediate import CandidateMatch, LineageEntry, TaxonMatch, TaxonMatchStatus

_STATUS = {
    TaxonMatchStatus.RESOLVED: WeaveStatus.OK,
    TaxonMatchStatus.FUZZY_UNIQUE: WeaveStatus.OK,
    TaxonMatchStatus.AMBIGUOUS: WeaveStatus.AMBIGUOUS,
    TaxonMatchStatus.NO_MATCH: WeaveStatus.NO_MATCH,
    TaxonMatchStatus.ERROR: WeaveStatus.ERROR,
}


def confidence_from_score(score: float | None) -> float:
    """Normalize a resolver score to a [0, 1] confidence.

    The underlying resolver is inconsistent: exact matches carry ``1.0`` (already
    a fraction) while fuzzy candidates carry a 0..100 RapidFuzz score. Disambiguate
    by magnitude — fuzzy scores are always well above 1.0.
    """
    if score is None:
        return 1.0
    if score <= 1.0:
        return float(score)
    return min(score / 100.0, 1.0)


def _lineage_value(lineage: list[LineageEntry]) -> list[dict]:
    return [{"taxid": e.taxid, "rank": e.rank, "name": e.name} for e in lineage]


def _candidate_result(candidate: CandidateMatch, provenance: tuple[str, ...]) -> CandidateResult:
    conf = confidence_from_score(candidate.score)
    strands = (
        Strand(vocab.TAXON_ID, candidate.taxid, confidence=conf, provenance=provenance),
        Strand(vocab.SCIENTIFIC_NAME, candidate.name, confidence=conf, provenance=provenance),
        Strand(vocab.TAXON_RANK, candidate.rank, confidence=conf, provenance=provenance),
    )
    return CandidateResult(strands=strands, confidence=conf)


def map_taxon_match(
    match: TaxonMatch,
    *,
    capability: Capability,
    requested_outputs: frozenset[str],
    backend: str,
    weaver_version: str,
) -> WeaveResult:
    triggered = capability.triggered_groups(requested_outputs)
    computed_groups = frozenset(triggered | {"core"})  # core is always computed internally
    allowed = capability.outputs_to_compute(requested_outputs)
    status = _STATUS[match.status]
    conf = confidence_from_score(match.score)
    provenance = (f"ncbi:{backend}",)

    strands: list[Strand] = []
    candidates: tuple[CandidateResult, ...] = ()
    errors: tuple[str, ...] = ()
    requires_review = match.requires_review

    if status is WeaveStatus.OK:
        if match.status is TaxonMatchStatus.FUZZY_UNIQUE:
            requires_review = True

        def add(type_id: str, value) -> None:
            if type_id in allowed and value is not None:
                strands.append(Strand(type_id, value, confidence=conf, provenance=provenance))

        add(vocab.TAXON_ID, match.taxid)
        add(vocab.SCIENTIFIC_NAME, match.scientific_name)
        add(vocab.TAXON_RANK, match.rank)
        add(vocab.PARENT_ID, match.parent_taxid)
        add(vocab.MATCH_TYPE, match.match_type)
        add(vocab.REVIEW_REQUIRED, match.requires_review)
        if vocab.LINEAGE in allowed:
            add(vocab.LINEAGE, _lineage_value(match.lineage))
    elif status is WeaveStatus.AMBIGUOUS:
        candidates = tuple(_candidate_result(c, provenance) for c in match.candidates)
        requires_review = True
    elif status is WeaveStatus.ERROR:
        errors = (match.error or "backend error",)

    return WeaveResult(
        capability_id=capability.id,
        weaver_version=weaver_version,
        backend_used=backend,
        computed_groups=computed_groups,
        status=status,
        strands=tuple(strands),
        candidates=candidates,
        warnings=tuple(match.warnings),
        errors=errors,
        requires_review=requires_review,
    )
