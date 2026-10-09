"""Observed percentage units and exact nonnegative counts are not silently coerced."""

import pytest
from gmrepo_weaver import setup


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "-Infinity", -1, 100.1, True, "bad"])
def test_invalid_percentages_preserve_field_and_raw_context(value):
    with pytest.raises(setup._InvalidResponse, match="relative_abundance") as exc:
        setup._num(value, field="relative_abundance", maximum=100)
    assert repr(value) in str(exc.value)


@pytest.mark.parametrize("value", ["nan", float("inf"), -1, "1.5", True, 2**63])
def test_invalid_counts_never_truncate_or_overflow(value):
    with pytest.raises(setup._InvalidResponse, match="samples"):
        setup._int(value, field="samples")


def test_valid_boundaries_missing_and_exact_large_counts():
    assert setup._num(None) is None
    assert setup._num("0", maximum=100) == 0
    assert setup._num("100", maximum=100) == 100
    assert setup._int(None) is None
    assert setup._int("9007199254740993") == 9007199254740993
    assert setup._int("3.0") == 3
    assert setup._prevalence(0, 0) is None
    assert setup._prevalence(1, 4) == 25
    with pytest.raises(setup._InvalidResponse, match="exceeds"):
        setup._prevalence(5, 4)


@pytest.mark.parametrize(
    "field", ["prevalence_percentage", "abundance_mean", "abundance_median", "abundance_sd"]
)
def test_caller_supplied_invalid_association_is_rejected_before_file_creation(tmp_path, field):
    path = tmp_path / "invalid.sqlite"
    with pytest.raises(setup._InvalidResponse, match=field):
        setup.write_db(
            path,
            overview=[],
            associations=[
                {"ncbi_taxon_id": 816, "rank": "genus", "mesh_id": "D1", field: float("nan")}
            ],
            phenotypes=[],
        )
    assert not path.exists()


def test_profile_percentage_and_association_count_validation():
    with pytest.raises(setup._InvalidResponse, match="relative_abundance"):
        setup._run_profile_rows(
            "D1", "R1", {"species": [{"ncbi_taxon_id": 1, "relative_abundance": 101}]}
        )
    with pytest.raises(setup._InvalidResponse, match="exceeds"):
        setup._taxon_associations(
            816, {"phenotypes_associated_with_taxon": [{"samples": 5, "valid_runs": 4}]}
        )
