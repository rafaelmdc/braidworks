"""License-driven citation requirements for weaver provenance.

The "license preferences" of issue #1: a small table mapping a license identifier
(ideally SPDX, e.g. ``CC-BY-4.0`` / ``CC0-1.0``) to *how* a source that ships under
it must be credited. This is what turns a :class:`~braidworks.core.capability.Provenance`
into an automatic reference — the license drives the form of the citation.

Lives in core (not weaverkit) because both the runtime reference emission and the
weaverkit dev tooling (verify guard, ``references`` CLI, view) consume it, and core is
the shared base both depend on.
"""

from __future__ import annotations

# Citation requirement levels, weakest to strongest obligation.
CITE_REQUESTED = "cite_requested"  # public-domain / CC0: crediting requested, not required
ATTRIBUTION_REQUIRED = "attribution_required"  # CC-BY family: attribution legally required
RESTRICTED = "restricted"  # unknown / non-open: surface a warning, confirm reuse terms

# Known license identifiers -> requirement level. Keys are the values weavers should
# put in ``[weaver].license``; an id absent here classifies as RESTRICTED so an
# unvetted license is visible rather than silently treated as free.
LICENSE_RULES: dict[str, str] = {
    "CC0-1.0": CITE_REQUESTED,
    "Public Domain": CITE_REQUESTED,
    "Open": CITE_REQUESTED,
    "CC-BY-3.0": ATTRIBUTION_REQUIRED,
    "CC-BY-4.0": ATTRIBUTION_REQUIRED,
    "CC-BY-SA-4.0": ATTRIBUTION_REQUIRED,
}


def is_known_license(license_id: str) -> bool:
    """True if ``license_id`` is a recognized identifier in :data:`LICENSE_RULES`."""
    return license_id in LICENSE_RULES


def citation_requirement(license_id: str) -> str:
    """Requirement level for a license id; unknown ids are :data:`RESTRICTED`."""
    return LICENSE_RULES.get(license_id, RESTRICTED)
