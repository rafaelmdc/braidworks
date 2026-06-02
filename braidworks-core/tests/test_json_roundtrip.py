"""Every dataclass round-trips through to_json/from_json without data loss."""

from __future__ import annotations

import json

from braidworks.core.braid import (
    Braid,
    CapabilityInvocation,
    FallbackCondition,
)
from braidworks.core.executor import ExecutionError, ExecutionResult, ReviewQueueItem
from braidworks.core.result import CandidateResult, WeaveResult, WeaveStatus
from braidworks.core.strand import Strand, StrandSet

from helpers import resolve_name_capability, manifest


def _json_stable(obj) -> str:
    """Serialize to JSON and back to confirm it is genuinely JSON-serializable."""
    return json.dumps(obj.to_json(), sort_keys=True)


def test_strand_roundtrip():
    s = Strand("organism.name", "Homo sapiens", confidence=0.85, provenance=("ncbi",), metadata={"k": 1})
    again = Strand.from_json(s.to_json())
    assert again == s
    assert again.provenance == ("ncbi",)
    _json_stable(s)


def test_strand_collection_value_roundtrip():
    s = Strand("ncbi.assembly.ids", [1, 2, 3])
    assert Strand.from_json(s.to_json()) == s


def test_strandset_roundtrip():
    ss = StrandSet.from_strands("e1", [Strand("organism.name", "Mus musculus")])
    ss.requires_review = True
    ss.warnings.append("w")
    ss.errors.append("err")
    again = StrandSet.from_json(ss.to_json())
    assert again.entity_id == "e1"
    assert again.get("organism.name").value == "Mus musculus"
    assert again.requires_review is True
    assert again.warnings == ["w"] and again.errors == ["err"]
    _json_stable(ss)


def test_capability_and_manifest_roundtrip():
    cap = resolve_name_capability()
    again = type(cap).from_json(cap.to_json())
    assert again == cap
    man = manifest(cap)
    assert type(man).from_json(man.to_json()) == man
    _json_stable(man)


def test_weaveresult_and_candidate_roundtrip():
    cand = CandidateResult(strands=(Strand("ncbi.taxon.id", 9606),), confidence=0.9, metadata={"x": "y"})
    wr = WeaveResult(
        capability_id="ncbi.resolve_name",
        capability_version="1.0.0",
        backend_used="local",
        computed_groups=frozenset({"core", "lineage"}),
        status=WeaveStatus.AMBIGUOUS,
        strands=(),
        candidates=(cand,),
        warnings=("w1",),
        errors=(),
        requires_review=True,
    )
    again = WeaveResult.from_json(wr.to_json())
    assert again == wr
    _json_stable(wr)


def test_braid_roundtrip():
    inv = CapabilityInvocation(
        weaver_id="ncbi",
        capability_id="ncbi.resolve_name",
        input_types=frozenset({"organism.name"}),
        output_types=frozenset({"ncbi.taxon.id"}),
        primary_backend="local",
        fallback_backends=("api",),
        fallback_on=frozenset({FallbackCondition.NO_MATCH}),
    )
    braid = Braid(steps=(inv,), from_types=frozenset({"organism.name"}), to_types=frozenset({"ncbi.taxon.id"}))
    again = Braid.from_json(braid.to_json())
    assert again == braid
    _json_stable(braid)


def test_review_queue_item_roundtrip():
    inv = CapabilityInvocation(
        weaver_id="ncbi",
        capability_id="ncbi.resolve_taxid",
        input_types=frozenset({"ncbi.taxon.id"}),
        output_types=frozenset({"ncbi.taxon.lineage"}),
        primary_backend="local",
    )
    wr = WeaveResult(
        capability_id="ncbi.resolve_name",
        capability_version="1.0.0",
        backend_used="local",
        computed_groups=frozenset({"core"}),
        status=WeaveStatus.AMBIGUOUS,
    )
    item = ReviewQueueItem(
        strand_set=StrandSet.from_strands("e1", [Strand("organism.name", "E. coli")]),
        triggering_result=wr,
        remaining_steps=(inv,),
    )
    again = ReviewQueueItem.from_json(item.to_json())
    assert again.strand_set.entity_id == "e1"
    assert again.triggering_result.status is WeaveStatus.AMBIGUOUS
    assert again.remaining_steps == (inv,)
    _json_stable(item)


def test_execution_error_roundtrip():
    err = ExecutionError(
        strand_set=StrandSet.from_strands("e1", [Strand("organism.name", "x")]),
        error_type="MissingInputError",
        message="missing organism.name",
        step_index=None,
        capability_id=None,
    )
    again = ExecutionError.from_json(err.to_json())
    assert again == err
    # Must be JSON-serializable with no raw exception object.
    _json_stable(err)


def test_execution_result_roundtrip():
    res = ExecutionResult(
        resolved=[StrandSet.from_strands("ok", [Strand("ncbi.taxon.id", 9606)])],
        unresolved=[
            (
                StrandSet.from_strands("nm", [Strand("organism.name", "nope")]),
                WeaveResult(
                    capability_id="ncbi.resolve_name",
                    capability_version="1.0.0",
                    backend_used="local",
                    computed_groups=frozenset({"core"}),
                    status=WeaveStatus.NO_MATCH,
                ),
            )
        ],
    )
    again = ExecutionResult.from_json(res.to_json())
    assert again.resolved[0].get("ncbi.taxon.id").value == 9606
    assert again.unresolved[0][1].status is WeaveStatus.NO_MATCH
    assert again.total() == 2
    _json_stable(res)
