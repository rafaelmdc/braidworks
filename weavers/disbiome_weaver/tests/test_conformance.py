"""Conformance tests for disbiome_weaver — the weaver must match its spec.

This wires up weaverkit's WeaverConformanceTests, which checks the manifest,
reachability, and fingerprints, and runs the spec's golden examples (skipping when
the backend is not configured). Do not weaken these — they are the contract.
"""

from __future__ import annotations

from pathlib import Path

from disbiome_weaver.factory import build_disbiome_weaver_fixture

from weaverkit import WeaverConformanceTests

SPEC = str(Path(__file__).resolve().parent.parent / "weaver.spec.toml")


class TestConformance(WeaverConformanceTests):
    spec_path = SPEC
    golden_backend = "local"

    def build_weaver(self):
        # The real local backend builds from the network; the fixture wires the
        # same backend against a tiny canned SQLite, so golden runs deterministically
        # offline (matching `weaverkit verify --strict`).
        return build_disbiome_weaver_fixture()
