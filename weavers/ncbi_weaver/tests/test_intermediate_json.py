"""Public taxon intermediates retain enums/nested fields through actual JSON."""

import json

import pytest
from braidworks.core import UnsupportedCapability
from ncbi_weaver.backends.base import GeneBackend, GenomeBackend, ResolutionBackend
from ncbi_weaver.backends.datasets_v2 import DatasetsV2Backend
from ncbi_weaver.dispatch import BackendDispatchWeaver
from ncbi_weaver.intermediate import CandidateMatch, LineageEntry, TaxonMatch, TaxonMatchStatus


@pytest.mark.parametrize("status", list(TaxonMatchStatus))
def test_nested_match_json_roundtrip_and_detached_collections(status):
    ancestor = LineageEntry(1, "no rank", "root")
    candidate = CandidateMatch(2, "Candidate", "species", "fuzzy", 83.5, [ancestor])
    original = TaxonMatch(
        "query",
        status,
        taxid=2,
        scientific_name="Candidate",
        rank="species",
        parent_taxid=1,
        match_type="fuzzy",
        score=83.5,
        requires_review=True,
        candidates=[candidate],
        lineage=[ancestor],
        lineage_taxids=[1],
        warnings=["review"],
        error="detail" if status is TaxonMatchStatus.ERROR else None,
    )
    restored = TaxonMatch.from_json(json.loads(json.dumps(original.to_json())))
    assert restored == original and restored.status is status
    restored.candidates[0].lineage[0].name = "changed"
    restored.warnings.append("new")
    assert original.lineage[0].name == "root" and original.warnings == ["review"]
    assert CandidateMatch.from_json(json.loads(json.dumps(candidate.to_json()))) == candidate
    assert LineageEntry.from_json(json.loads(json.dumps(ancestor.to_json()))) == ancestor


def test_resolution_protocol_has_no_unsupported_operations():
    assert not hasattr(ResolutionBackend, "describe_gene")
    backend = DatasetsV2Backend()
    assert isinstance(backend, ResolutionBackend)
    assert isinstance(backend, GenomeBackend) and isinstance(backend, GeneBackend)


def test_missing_optional_operation_raises_structural_error():
    with pytest.raises(UnsupportedCapability, match="list_children"):
        BackendDispatchWeaver._operation(object(), "list_children")
