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

WEAVER_ID = "example"
WEAVER_VERSION = "1.0.7"
WEAVER_TITLE = "Example reference weaver (taxid -> traits, from a tiny CSV)"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://github.com/rafaelmdc/braidworks/blob/main/weavers/example_weaver/src/example_weaver/data/example_traits.csv",
    license="CC0-1.0",
    citation="",
    attribution="Braidworks bundled sample data",
)

# What each consumed/produced type means — from the spec's [types] table, else
# weaverkit's key registry. Lets users find fields by meaning.
TYPE_DESCRIPTIONS = {
    "microbe.trait.gram_stain": "This microbe's Gram stain — positive or negative.",
    "microbe.trait.optimum_temp": "The temperature this microbe grows best at.",
    "ncbi.taxon.id": "NCBI Taxonomy id for one organism — the main organism join key.",
}


def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:
    """Declare every capability for the wired-in backends."""
    return WeaverManifest(
        weaver_id=WEAVER_ID,
        version=WEAVER_VERSION,
        title=WEAVER_TITLE,
        provenance=PROVENANCE,
        type_descriptions=dict(TYPE_DESCRIPTIONS),
        capabilities=(
            Capability(
                id="describe_traits",
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
