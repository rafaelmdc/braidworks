"""Capabilities and manifest for the weaver — generated from weaver.spec.toml.

The manifest is the machine-readable mirror of the spec; keep them in sync
(``weaverkit verify`` checks this). Edit the spec and regenerate rather than
hand-editing capabilities here.
"""

from __future__ import annotations

from braidworks.core import Capability, OutputGroup, Provenance, WeaverManifest

WEAVER_ID = "reactome"
WEAVER_VERSION = "0.1.1"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://reactome.org",
    license="CC0-1.0",
    citation="https://doi.org/10.1093/nar/gkab1028",
    attribution="Reactome",
)


def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:
    """Declare every capability for the wired-in backends."""
    return WeaverManifest(
        weaver_id=WEAVER_ID,
        version=WEAVER_VERSION,
        provenance=PROVENANCE,
        capabilities=(
            Capability(
                id="resolve_pathways",
                consumes=frozenset({"protein.uniprot.accession"}),
                produces=frozenset(
                    {"pathway.reactome.count", "pathway.reactome.names", "pathway.reactome.records"}
                ),
                output_groups=(
                    OutputGroup(
                        id="summary",
                        outputs=frozenset({"pathway.reactome.count", "pathway.reactome.names"}),
                    ),
                    OutputGroup(id="full", outputs=frozenset({"pathway.reactome.records"})),
                ),
                backends=backends,
                max_batch_size=25,
            ),
        ),
    )
