"""Capability.triggered_groups and outputs_to_compute."""

from __future__ import annotations

from braidworks.core import Provenance, WeaverManifest
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


def test_manifest_without_provenance_round_trips_and_omits_key():
    cap = resolve_name_capability()
    manifest = WeaverManifest(weaver_id="taxon", version="1.0.0", capabilities=(cap,))
    data = manifest.to_json()
    assert "provenance" not in data  # absent, not null, when unset
    assert WeaverManifest.from_json(data) == manifest
    assert manifest.provenance is None


def test_manifest_title_round_trips_and_omits_when_empty():
    cap = resolve_name_capability()
    bare = WeaverManifest(weaver_id="taxon", version="1.0.0", capabilities=(cap,))
    assert "title" not in bare.to_json()
    assert bare.title == ""

    titled = WeaverManifest(
        weaver_id="taxon", version="1.0.0", capabilities=(cap,), title="NCBI taxonomy"
    )
    assert titled.to_json()["title"] == "NCBI taxonomy"
    assert WeaverManifest.from_json(titled.to_json()) == titled


def test_manifest_with_provenance_round_trips():
    cap = resolve_name_capability()
    prov = Provenance(
        source_url="https://www.uniprot.org",
        license="CC-BY-4.0",
        citation="https://doi.org/10.1093/nar/gkac1052",
        attribution="UniProt Consortium",
    )
    manifest = WeaverManifest(
        weaver_id="uniprot", version="0.1.0", capabilities=(cap,), provenance=prov
    )
    data = manifest.to_json()
    assert data["provenance"]["license"] == "CC-BY-4.0"
    assert WeaverManifest.from_json(data) == manifest


def test_provenance_is_empty():
    assert Provenance().is_empty()
    assert not Provenance(license="CC0-1.0").is_empty()
