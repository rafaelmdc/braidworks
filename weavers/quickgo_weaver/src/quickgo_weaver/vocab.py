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

WEAVER_ID = "quickgo"
WEAVER_VERSION = "0.1.8"
WEAVER_TITLE = "Gene Ontology annotations (accession -> GO terms by aspect)"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://www.ebi.ac.uk/QuickGO",
    license="CC-BY-4.0",
    citation="https://doi.org/10.1093/bioinformatics/btp536",
    attribution="Gene Ontology / EMBL-EBI QuickGO",
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
                id="list_go_terms",
                consumes=frozenset({"protein.uniprot.accession"}),
                produces=frozenset(
                    {
                        "go.annotation.coverage",
                        "go.annotation.records",
                        "go.biological_process",
                        "go.cellular_component",
                        "go.count",
                        "go.molecular_function",
                        "go.records",
                        "go.term",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="aspects",
                        outputs=frozenset(
                            {
                                "go.biological_process",
                                "go.cellular_component",
                                "go.molecular_function",
                            }
                        ),
                    ),
                    OutputGroup(id="summary", outputs=frozenset({"go.count", "go.term"})),
                    OutputGroup(id="full", outputs=frozenset({"go.records"})),
                    OutputGroup(id="annotations", outputs=frozenset({"go.annotation.records"})),
                    OutputGroup(id="coverage", outputs=frozenset({"go.annotation.coverage"})),
                ),
                backends=backends,
                max_batch_size=10,
                set_outputs=frozenset({"go.term"}),
            ),
            Capability(
                id="describe_go_term",
                consumes=frozenset({"go.term"}),
                produces=frozenset(
                    {"go.term.aspect", "go.term.definition", "go.term.detail", "go.term.name"}
                ),
                output_groups=(
                    OutputGroup(
                        id="detail",
                        outputs=frozenset(
                            {
                                "go.term.aspect",
                                "go.term.definition",
                                "go.term.detail",
                                "go.term.name",
                            }
                        ),
                    ),
                ),
                backends=backends,
                max_batch_size=10,
            ),
        ),
    )
