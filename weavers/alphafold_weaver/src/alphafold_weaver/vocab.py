"""Capabilities and manifest for the weaver — generated from weaver.spec.toml.

The manifest is the machine-readable mirror of the spec; keep them in sync
(``weaverkit verify`` checks this). Edit the spec and regenerate rather than
hand-editing capabilities here.
"""

from __future__ import annotations

from braidworks.core import Capability, OutputGroup, Provenance, WeaverManifest

WEAVER_ID = "alphafold"
WEAVER_VERSION = "0.1.0"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://alphafold.ebi.ac.uk",
    license="CC-BY-4.0",
    citation="https://doi.org/10.1093/nar/gkab1061",
    attribution="AlphaFold DB (Google DeepMind & EMBL-EBI)",
)


def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:
    """Declare every capability for the wired-in backends."""
    return WeaverManifest(
        weaver_id=WEAVER_ID,
        version=WEAVER_VERSION,
        provenance=PROVENANCE,
        capabilities=(
            Capability(
                id="resolve_model",
                consumes=frozenset({"protein.uniprot.accession"}),
                produces=frozenset(
                    {
                        "structure.alphafold.entry_id",
                        "structure.alphafold.mean_plddt",
                        "structure.alphafold.model_url",
                        "structure.alphafold.pae_image_url",
                        "structure.alphafold.records",
                        "structure.alphafold.version",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="model",
                        outputs=frozenset(
                            {
                                "structure.alphafold.entry_id",
                                "structure.alphafold.mean_plddt",
                                "structure.alphafold.model_url",
                                "structure.alphafold.pae_image_url",
                                "structure.alphafold.version",
                            }
                        ),
                    ),
                    OutputGroup(id="full", outputs=frozenset({"structure.alphafold.records"})),
                ),
                backends=backends,
                max_batch_size=25,
            ),
        ),
    )
