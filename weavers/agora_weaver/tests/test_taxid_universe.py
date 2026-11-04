"""Explicit membership shares its source with lookup and implies no artifact coverage."""

import pytest
from agora_weaver import crosswalk_taxids, dataset


def test_universe_matches_full_crosswalk_and_canonical_ids():
    crosswalk = dataset.load_crosswalk()
    observed = crosswalk_taxids()
    assert observed == frozenset(int(key) for key in crosswalk)
    assert observed
    assert all(dataset.reconstructions_for(taxid) for taxid in observed)
    assert all(isinstance(taxid, int) for taxid in observed)
    with pytest.raises(AttributeError):
        observed.add(999999999)


def test_membership_is_exact_and_does_not_acquire_resources(monkeypatch):
    monkeypatch.setattr(dataset, "_crosswalk_index", lambda: {"562": (("model_a", "GCF_1.1"),)})
    assert crosswalk_taxids() == frozenset({562})
    assert {int(value) for value in ["562", "561", "2"]} & crosswalk_taxids() == {562}
    # Neither genus/ancestor inference nor a reaction DB/SBML check is involved.
    assert dataset.reconstructions_for("561") == []
    assert dataset.reconstructions_for("562")[0]["reconstruction_id"] == "model_a"
