"""Capabilities and manifest for the weaver — generated from weaver.spec.toml.

The manifest is the machine-readable mirror of the spec; keep them in sync
(``weaverkit verify`` checks this). Edit the spec and regenerate rather than
hand-editing capabilities here.
"""

from __future__ import annotations

from braidworks.core import Capability, OutputGroup, WeaverManifest

WEAVER_ID = "uniprot"
WEAVER_VERSION = "0.1.0"


def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:
    """Declare every capability for the wired-in backends."""
    return WeaverManifest(
        weaver_id=WEAVER_ID,
        version=WEAVER_VERSION,
        capabilities=(
            Capability(
                id="resolve_protein",
                consumes=frozenset({"protein.query"}),
                produces=frozenset(
                    {
                        "ncbi.taxon.id",
                        "protein.function",
                        "protein.gene",
                        "protein.length",
                        "protein.name",
                        "protein.organism",
                        "protein.reviewed",
                        "protein.uniprot.accession",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="identity",
                        outputs=frozenset(
                            {
                                "protein.gene",
                                "protein.name",
                                "protein.organism",
                                "protein.reviewed",
                                "protein.uniprot.accession",
                            }
                        ),
                    ),
                    OutputGroup(id="taxonomy", outputs=frozenset({"ncbi.taxon.id"})),
                    OutputGroup(
                        id="function", outputs=frozenset({"protein.function", "protein.length"})
                    ),
                ),
                backends=backends,
                max_batch_size=25,
                always_computed_groups=frozenset({"identity"}),
            ),
        ),
    )
