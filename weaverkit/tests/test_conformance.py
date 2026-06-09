"""Conformance-check tests.

A conforming fake weaver must pass every check; deliberately derailed manifests
must make the matching check fire. This is the test-of-the-tests: it proves the
guardrail actually catches the defects it claims to.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from braidworks.core.capability import Capability, OutputGroup

from weaverkit.conformance import (
    WeaverConformanceTests,
    check_fingerprints,
    check_golden,
    check_manifest,
)
from weaverkit.spec import load_spec

from tests.fakes import ConformingFakeWeaver, UnknownFingerprintWeaver

FIXTURE = Path(__file__).parent / "fixtures" / "valid.weaver.spec.toml"


def _spec():
    return load_spec(FIXTURE)


def _manifest():
    return ConformingFakeWeaver.MANIFEST


def _with_capabilities(manifest, capabilities):
    return dataclasses.replace(manifest, capabilities=tuple(capabilities))


# --- check_manifest: happy path ---------------------------------------------


def test_conforming_manifest_passes():
    assert check_manifest(_manifest(), _spec()) == []


# --- check_manifest: negative cases -----------------------------------------


def test_weaver_id_mismatch_caught():
    bad = dataclasses.replace(_manifest(), weaver_id="wrong")
    problems = check_manifest(bad, _spec())
    assert any("weaver_id" in p for p in problems)


def test_missing_capability_caught():
    bad = _with_capabilities(_manifest(), [])
    problems = check_manifest(bad, _spec())
    assert any("but the manifest does not" in p for p in problems)


def test_extra_capability_caught():
    extra = Capability(
        id="ghost",
        consumes=frozenset({"ncbi.taxon.id"}),
        produces=frozenset({"microbe.trait.metabolism"}),
        output_groups=(OutputGroup(id="g", outputs=frozenset({"microbe.trait.metabolism"})),),
        backends=("local",),
    )
    bad = _with_capabilities(_manifest(), [*_manifest().capabilities, extra])
    problems = check_manifest(bad, _spec())
    assert any("not in the spec" in p for p in problems)


def test_consumes_mismatch_caught():
    cap = _manifest().capabilities[0]
    bad_cap = dataclasses.replace(cap, consumes=frozenset({"organism.scientific_name"}))
    bad = _with_capabilities(_manifest(), [bad_cap])
    problems = check_manifest(bad, _spec())
    assert any("consumes" in p for p in problems)


def test_unreachable_consumes_in_manifest_caught():
    cap = _manifest().capabilities[0]
    bad_cap = dataclasses.replace(cap, consumes=frozenset({"madin.private.id"}))
    bad = _with_capabilities(_manifest(), [bad_cap])
    problems = check_manifest(bad, _spec())
    assert any("not a registered" in p for p in problems)


def test_produces_mismatch_caught():
    cap = _manifest().capabilities[0]
    bad_cap = dataclasses.replace(cap, produces=frozenset({"microbe.trait.metabolism"}))
    bad = _with_capabilities(_manifest(), [bad_cap])
    problems = check_manifest(bad, _spec())
    assert any("produces" in p for p in problems)


def test_output_group_mismatch_caught():
    cap = _manifest().capabilities[0]
    bad_cap = dataclasses.replace(
        cap,
        output_groups=(
            OutputGroup(
                id="traits.core",
                outputs=frozenset(
                    {
                        "microbe.trait.metabolism",
                        "microbe.trait.gram_stain",
                        "microbe.trait.optimum_temp",
                    }
                ),
            ),
        ),
    )
    bad = _with_capabilities(_manifest(), [bad_cap])
    problems = check_manifest(bad, _spec())
    assert any("output groups" in p for p in problems)


def test_backend_not_in_spec_caught():
    cap = _manifest().capabilities[0]
    bad_cap = dataclasses.replace(cap, backends=("local", "api"))
    bad = _with_capabilities(_manifest(), [bad_cap])
    problems = check_manifest(bad, _spec())
    assert any("not in the" in p and "backends" in p for p in problems)


# --- check_fingerprints ------------------------------------------------------


def test_good_fingerprints_pass():
    assert check_fingerprints(ConformingFakeWeaver(), ["local"]) == []


def test_unknown_fingerprint_caught():
    problems = check_fingerprints(UnknownFingerprintWeaver(), ["local"])
    assert any("unknown" in p.lower() for p in problems)


# --- golden runner -----------------------------------------------------------


async def test_golden_passes_for_conforming_weaver():
    problems = await check_golden(ConformingFakeWeaver(), _spec(), backend="local")
    assert problems == []


async def test_golden_detects_wrong_value():
    spec = _spec()
    # Rewrite the golden to expect a value the fake won't produce.
    bad_golden = dataclasses.replace(
        spec.golden[0], expect={"microbe.trait.gram_stain": "positive"}
    )
    spec = dataclasses.replace(spec, golden=(bad_golden,))
    problems = await check_golden(ConformingFakeWeaver(), spec, backend="local")
    assert any("expected" in p for p in problems)


# --- the mixin itself --------------------------------------------------------


class TestConformanceMixin(WeaverConformanceTests):
    spec_path = str(FIXTURE)
    golden_backend = "local"

    def build_weaver(self):
        return ConformingFakeWeaver()


# --- canonical-type / shared-key parity --------------------------------------


def test_every_shared_key_has_a_canonical_type():
    """Lockstep contract: weaverkit.keys.SHARED_KEYS and core CANONICAL_TYPES.

    Core declares one value type per shared (bridge) key; the reachability registry
    lives here in weaverkit. They must stay in sync, or a new shared key would have
    no declared shape (cache/join fragmentation) — caught here at CI time.
    """
    from braidworks.core import CANONICAL_TYPES

    from weaverkit.keys import SHARED_KEYS

    missing = sorted(set(SHARED_KEYS) - set(CANONICAL_TYPES))
    assert not missing, (
        "shared keys with no canonical type in braidworks.core.keytypes: "
        f"{missing} — add them to CANONICAL_TYPES"
    )
    extra = sorted(set(CANONICAL_TYPES) - set(SHARED_KEYS))
    assert not extra, (
        "CANONICAL_TYPES declares keys that are not registered shared keys: "
        f"{extra} — add them to weaverkit.keys.SHARED_KEYS or drop them"
    )


def test_unconfigured_fingerprint_is_not_treated_as_configured():
    """#1 regression: an ``unconfigured:<backend>`` sentinel must not run golden."""
    from weaverkit.conformance import _is_configured_fingerprint

    assert not _is_configured_fingerprint("unconfigured:local")
    assert not _is_configured_fingerprint("")
    assert not _is_configured_fingerprint("unknown")
    assert _is_configured_fingerprint("disbiome@2024-01-01")
