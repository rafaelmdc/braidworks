"""Capabilities and manifest for the weaver — generated from weaver.spec.toml.

The manifest is the machine-readable mirror of the spec; keep them in sync
(``weaverkit verify`` checks this). Edit the spec and regenerate rather than
hand-editing capabilities here.
"""

from __future__ import annotations

from braidworks.core import Capability, OutputGroup, Provenance, WeaverManifest

WEAVER_ID = "example"
WEAVER_VERSION = "1.0.0"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://github.com/rafaelcorreia/braidworks (bundled sample data)",
    license="CC0-1.0",
    citation="",
    attribution="Braidworks bundled sample data",
)


def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:
    """Declare every capability for the wired-in backends."""
    return WeaverManifest(
        weaver_id=WEAVER_ID,
        version=WEAVER_VERSION,
        provenance=PROVENANCE,
        capabilities=(
            Capability(
                id="resolve_traits",
                consumes=frozenset({"ncbi.taxon.id"}),
                produces=frozenset({"microbe.trait.gram_stain", "microbe.trait.optimum_temp"}),
                output_groups=(
                    OutputGroup(id="traits.core", outputs=frozenset({"microbe.trait.gram_stain"})),
                    OutputGroup(
                        id="traits.growth", outputs=frozenset({"microbe.trait.optimum_temp"})
                    ),
                ),
                backends=backends,
            ),
        ),
    )
