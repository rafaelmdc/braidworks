"""Capabilities and manifest for the weaver — generated from weaver.spec.toml.

The manifest is the machine-readable mirror of the spec; keep them in sync
(``weaverkit verify`` checks this). Edit the spec and regenerate rather than
hand-editing capabilities here.
"""

from __future__ import annotations

from braidworks.core import (
    Capability,
    OutputGroup,
    Provenance,
    WeaverManifest,
)

WEAVER_ID = "faprotax"
WEAVER_VERSION = "0.1.0"
WEAVER_TITLE = "FAPROTAX ecological function (organism lineage -> functional groups)"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://pages.uoregon.edu/slouca/LoucaLab/archive/FAPROTAX/",
    license="Open",
    citation="https://doi.org/10.1126/science.aaf4507",
    attribution="FAPROTAX (Louca, Parfrey & Doebeli 2016); DB (c) Stilianos Louca",
)


def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:
    """Declare every capability for the wired-in backends."""
    return WeaverManifest(
        weaver_id=WEAVER_ID,
        version=WEAVER_VERSION,
        title=WEAVER_TITLE,
        provenance=PROVENANCE,
        capabilities=(
            Capability(
                id="describe_ecology",
                consumes=frozenset({"ncbi.taxon.lineage"}),
                produces=frozenset({"microbe.ecology.functional_groups"}),
                output_groups=(
                    OutputGroup(
                        id="ecology", outputs=frozenset({"microbe.ecology.functional_groups"})
                    ),
                ),
                backends=backends,
            ),
        ),
    )
