"""Capabilities and manifest for the weaver — generated from weaver.spec.toml.

The manifest is the machine-readable mirror of the spec; keep them in sync
(``weaverkit verify`` checks this). Edit the spec and regenerate rather than
hand-editing capabilities here.
"""

from __future__ import annotations

from braidworks.core import Capability, OutputGroup, Provenance, WeaverManifest

WEAVER_ID = "string"
WEAVER_VERSION = "0.1.3"
WEAVER_TITLE = "STRING protein-protein interactions (accession -> partners + scores)"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://string-db.org",
    license="CC-BY-4.0",
    citation="https://doi.org/10.1093/nar/gkac1000",
    attribution="STRING (Szklarczyk et al.)",
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
                id="resolve_interactions",
                consumes=frozenset({"protein.uniprot.accession"}),
                produces=frozenset(
                    {
                        "protein.query",
                        "protein.interaction.count",
                        "protein.interaction.partners",
                        "protein.interaction.records",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="summary",
                        outputs=frozenset(
                            {
                                "protein.query",
                                "protein.interaction.count",
                                "protein.interaction.partners",
                            }
                        ),
                    ),
                    OutputGroup(id="full", outputs=frozenset({"protein.interaction.records"})),
                ),
                set_outputs=frozenset({"protein.query"}),
                backends=backends,
                max_batch_size=25,
            ),
        ),
    )
