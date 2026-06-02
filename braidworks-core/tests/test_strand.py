"""StrandSet.merge_result and add_strand merge policies."""

from __future__ import annotations

from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import MergePolicy, Strand, StrandSet


def _result(*strands: Strand, requires_review: bool = False) -> WeaveResult:
    return WeaveResult(
        capability_id="cap",
        capability_version="1",
        backend_used="local",
        computed_groups=frozenset({"core"}),
        status=WeaveStatus.OK,
        strands=strands,
        requires_review=requires_review,
    )


def test_highest_confidence_keeps_higher():
    ss = StrandSet.from_strands("e", [Strand("t", "low", confidence=0.5)])
    ss.merge_result(_result(Strand("t", "high", confidence=0.9)), MergePolicy.HIGHEST_CONFIDENCE)
    assert ss.get("t").value == "high"
    # A lower-confidence later strand does not displace the higher one.
    ss.merge_result(_result(Strand("t", "lower", confidence=0.1)), MergePolicy.HIGHEST_CONFIDENCE)
    assert ss.get("t").value == "high"


def test_first_wins_never_overwrites():
    ss = StrandSet.from_strands("e", [Strand("t", "orig", confidence=0.1)])
    ss.merge_result(_result(Strand("t", "new", confidence=0.99)), MergePolicy.FIRST_WINS)
    assert ss.get("t").value == "orig"


def test_last_wins_always_overwrites():
    ss = StrandSet.from_strands("e", [Strand("t", "orig", confidence=0.99)])
    ss.merge_result(_result(Strand("t", "new", confidence=0.01)), MergePolicy.LAST_WINS)
    assert ss.get("t").value == "new"


def test_merge_result_propagates_review_and_messages():
    ss = StrandSet.from_strands("e", [])
    r = _result(Strand("t", "v"), requires_review=True)
    r = WeaveResult(
        capability_id=r.capability_id,
        capability_version=r.capability_version,
        backend_used=r.backend_used,
        computed_groups=r.computed_groups,
        status=r.status,
        strands=r.strands,
        warnings=("careful",),
        errors=("bad",),
        requires_review=True,
    )
    ss.merge_result(r)
    assert ss.requires_review is True
    assert ss.warnings == ["careful"]
    assert ss.errors == ["bad"]


def test_new_type_is_added():
    ss = StrandSet.from_strands("e", [])
    ss.merge_result(_result(Strand("t", "v")))
    assert ss.has("t") and ss.available_types() == frozenset({"t"})
