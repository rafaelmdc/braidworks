"""License-classification rules: id -> citation requirement."""

from __future__ import annotations

from braidworks.core import (
    ATTRIBUTION_REQUIRED,
    CITE_REQUESTED,
    RESTRICTED,
    citation_requirement,
    is_known_license,
)


def test_cc_by_requires_attribution():
    assert citation_requirement("CC-BY-4.0") == ATTRIBUTION_REQUIRED


def test_cc0_and_public_domain_request_citation():
    assert citation_requirement("CC0-1.0") == CITE_REQUESTED
    assert citation_requirement("Public Domain") == CITE_REQUESTED


def test_unknown_license_is_restricted():
    assert citation_requirement("Proprietary-EULA") == RESTRICTED
    assert not is_known_license("Proprietary-EULA")


def test_known_license():
    assert is_known_license("CC-BY-4.0")
    assert is_known_license("CC0-1.0")
