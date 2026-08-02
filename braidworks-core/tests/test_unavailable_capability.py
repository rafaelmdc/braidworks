"""Reporting for capabilities a weaver declares but cannot offer as configured.

A weaver whose capability has no configured backend leaves that capability out of its
manifest — correct, because the planner must never route to something that cannot run. The
failure mode is that it vanishes *silently*: the caller gets "no capability produces 'X'",
which reads as "no weaver can do this" and sends them off to write a capability that already
exists. These tests pin the two places that gap is now reported.
"""

from __future__ import annotations

import warnings

import pytest
from braidworks.core.capability import UnavailableCapability, WeaverManifest
from braidworks.core.exceptions import CapabilityUnavailableWarning, NoPathError
from braidworks.core.planner import Braider
from braidworks.core.registry import BraidRegistry
from helpers import FakeWeaver, resolve_name_capability

WITHHELD = UnavailableCapability(
    id="ncbi.list_children",
    produces=frozenset({"ncbi.taxon.children_records", "ncbi.taxon.id"}),
    requires_backends=("api",),
    hint="build_ncbi_weaver(enable_api=True)",
)


def _registry(*, withholding: bool) -> BraidRegistry:
    manifest = WeaverManifest(
        weaver_id="ncbi",
        version="1.0.0",
        capabilities=(resolve_name_capability(),),
        unavailable=(WITHHELD,) if withholding else (),
    )
    reg = BraidRegistry()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", CapabilityUnavailableWarning)
        reg.register(FakeWeaver(manifest))
    return reg


def test_registration_warns_naming_the_capability_and_the_fix() -> None:
    reg = BraidRegistry()
    manifest = WeaverManifest(
        weaver_id="ncbi",
        version="1.0.0",
        capabilities=(resolve_name_capability(),),
        unavailable=(WITHHELD,),
    )
    with pytest.warns(CapabilityUnavailableWarning) as caught:
        reg.register(FakeWeaver(manifest))
    message = str(caught[0].message)
    assert "ncbi.list_children" in message
    assert "api" in message
    assert "build_ncbi_weaver(enable_api=True)" in message


def test_no_warning_when_nothing_is_withheld() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", CapabilityUnavailableWarning)
        _registry(withholding=False)  # must not raise


def test_route_error_distinguishes_unconfigured_from_absent() -> None:
    """The message a caller actually hits — it must not read as 'this weaver cannot'."""
    braider = Braider(_registry(withholding=True))
    with pytest.raises(NoPathError) as err:
        braider.plan(
            frozenset({"ncbi.taxon.id"}), frozenset({"ncbi.taxon.children_records"})
        )
    message = str(err.value)
    assert "ncbi.list_children" in message
    assert "build_ncbi_weaver(enable_api=True)" in message
    assert "backend is not configured" in message


def test_route_error_stays_plain_for_a_genuinely_unknown_type() -> None:
    braider = Braider(_registry(withholding=True))
    with pytest.raises(NoPathError, match="no capability produces 'nothing.at.all'"):
        braider.plan(frozenset({"ncbi.taxon.id"}), frozenset({"nothing.at.all"}))


def test_unavailable_capability_round_trips_through_json() -> None:
    manifest = WeaverManifest(
        weaver_id="ncbi",
        version="1.0.0",
        capabilities=(resolve_name_capability(),),
        unavailable=(WITHHELD,),
    )
    assert WeaverManifest.from_json(manifest.to_json()).unavailable == (WITHHELD,)


def test_manifest_without_unavailable_omits_the_key() -> None:
    manifest = WeaverManifest(
        weaver_id="ncbi", version="1.0.0", capabilities=(resolve_name_capability(),)
    )
    assert "unavailable" not in manifest.to_json()


def test_describe_is_readable_without_a_hint() -> None:
    bare = UnavailableCapability(
        id="x.cap", produces=frozenset({"x.out"}), requires_backends=("api", "local")
    )
    assert bare.describe() == "x.cap (needs backend: api, local)"
