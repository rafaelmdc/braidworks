"""Capability.triggered_groups and outputs_to_compute."""

from __future__ import annotations

from helpers import CORE_OUTPUTS, LINEAGE_OUTPUTS, resolve_name_capability


def test_lineage_request_triggers_only_lineage_group():
    cap = resolve_name_capability()
    assert cap.triggered_groups(frozenset({"ncbi.taxon.lineage"})) == frozenset({"lineage"})


def test_core_request_triggers_only_core_group():
    cap = resolve_name_capability()
    assert cap.triggered_groups(frozenset({"ncbi.taxon.id"})) == frozenset({"core"})


def test_outputs_to_compute_does_not_leak_across_groups():
    cap = resolve_name_capability()
    # Requesting a core output yields only core outputs, no lineage.
    core = cap.outputs_to_compute(frozenset({"ncbi.taxon.id"}))
    assert core == CORE_OUTPUTS
    assert not (core & LINEAGE_OUTPUTS)
    # Requesting a lineage output yields only lineage outputs, no core.
    lineage = cap.outputs_to_compute(frozenset({"ncbi.taxon.lineage"}))
    assert lineage == LINEAGE_OUTPUTS
    assert not (lineage & CORE_OUTPUTS)


def test_requesting_both_triggers_both():
    cap = resolve_name_capability()
    req = frozenset({"ncbi.taxon.id", "ncbi.taxon.lineage"})
    assert cap.triggered_groups(req) == frozenset({"core", "lineage"})
    assert cap.outputs_to_compute(req) == CORE_OUTPUTS | LINEAGE_OUTPUTS
