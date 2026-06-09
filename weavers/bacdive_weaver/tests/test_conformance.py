"""Conformance tests for bacdive_weaver — the weaver must match its spec.

This wires up weaverkit's WeaverConformanceTests, which checks the manifest,
reachability, and fingerprints, and runs the spec's golden examples (skipping when
the backend is not configured). Do not weaken these — they are the contract.
"""

from __future__ import annotations

from pathlib import Path

from weaverkit import WeaverConformanceTests

from bacdive_weaver.factory import build_bacdive_weaver_fixture

SPEC = str(Path(__file__).resolve().parent.parent / "weaver.spec.toml")


class TestConformance(WeaverConformanceTests):
    spec_path = SPEC
    golden_backend = "api"

    def build_weaver(self):
        # The BacDive v2 API is keyless, so the api backend is always "configured"
        # and golden would otherwise hit the live service. Use the fixture-backed
        # weaver (canned responses) so conformance golden runs offline + deterministic.
        # The manifest/fingerprint are identical to the live build.
        return build_bacdive_weaver_fixture()
