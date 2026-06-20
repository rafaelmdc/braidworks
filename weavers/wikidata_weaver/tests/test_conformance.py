"""Conformance tests for wikidata_weaver — the weaver must match its spec.

This wires up weaverkit's WeaverConformanceTests, which checks the manifest,
reachability, and fingerprints, and runs the spec's golden examples (skipping when
the backend is not configured). Do not weaken these — they are the contract.
"""

from __future__ import annotations

from pathlib import Path

from weaverkit import WeaverConformanceTests

from wikidata_weaver import factory

SPEC = str(Path(__file__).resolve().parent.parent / "weaver.spec.toml")


class TestConformance(WeaverConformanceTests):
    spec_path = SPEC
    golden_backend = "api"

    def build_weaver(self):
        # Prefer the offline fixture builder so golden examples run in CI; fall
        # back to the zero-config introspection builder when no fixture exists.
        builder = (
            getattr(factory, "build_wikidata_weaver_fixture", None) or factory.build_wikidata_weaver
        )
        return builder()
