"""Capabilities and manifest for the weaver — generated from weaver.spec.toml.

The manifest is the machine-readable mirror of the spec; keep them in sync
(``weaverkit verify`` checks this). Edit the spec and regenerate rather than
hand-editing capabilities here.
"""

from __future__ import annotations

from braidworks.core import Capability, OutputGroup, Provenance, WeaverManifest

WEAVER_ID = "bacdive"
WEAVER_VERSION = "0.1.0"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://bacdive.dsmz.de",
    license="CC-BY-4.0",
    citation="https://doi.org/10.1093/nar/gkab961",
    attribution="BacDive (DSMZ)",
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
                consumes=frozenset({"organism.scientific_name"}),
                produces=frozenset(
                    {
                        "microbe.trait.cell_shape",
                        "microbe.trait.gram_stain",
                        "microbe.trait.motility",
                        "microbe.trait.optimum_ph",
                        "microbe.trait.optimum_temp",
                        "microbe.trait.oxygen_tolerance",
                        "microbe.trait.spore_formation",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="morphology",
                        outputs=frozenset(
                            {
                                "microbe.trait.cell_shape",
                                "microbe.trait.gram_stain",
                                "microbe.trait.motility",
                                "microbe.trait.spore_formation",
                            }
                        ),
                    ),
                    OutputGroup(
                        id="physiology", outputs=frozenset({"microbe.trait.oxygen_tolerance"})
                    ),
                    OutputGroup(
                        id="growth",
                        outputs=frozenset(
                            {"microbe.trait.optimum_ph", "microbe.trait.optimum_temp"}
                        ),
                    ),
                ),
                backends=backends,
                max_batch_size=50,
            ),
        ),
    )
