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

WEAVER_ID = "agora"
WEAVER_VERSION = "0.1.2"
WEAVER_TITLE = (
    "AGORA2 metabolic reconstructions (NCBI taxid -> reconstruction + reaction repertoire)"
)

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://www.vmh.life",
    license="CC-BY-NC-4.0",
    citation="https://doi.org/10.1038/s41587-022-01628-0",
    attribution="AGORA2 / Virtual Metabolic Human (VMH), Heinken et al., Nat Biotechnol 2023 (data CC BY-NC 4.0)",
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
                id="describe_metabolic_reconstruction",
                consumes=frozenset({"ncbi.taxon.id"}),
                produces=frozenset(
                    {"microbe.metabolism.reactions", "microbe.metabolism.reconstruction"}
                ),
                output_groups=(
                    OutputGroup(
                        id="core", outputs=frozenset({"microbe.metabolism.reconstruction"})
                    ),
                    OutputGroup(
                        id="reactions", outputs=frozenset({"microbe.metabolism.reactions"})
                    ),
                ),
                backends=backends,
                max_batch_size=50,
            ),
        ),
    )
