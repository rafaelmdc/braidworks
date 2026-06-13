"""Capabilities and manifest for the weaver — generated from weaver.spec.toml.

The manifest is the machine-readable mirror of the spec; keep them in sync
(``weaverkit verify`` checks this). Edit the spec and regenerate rather than
hand-editing capabilities here.
"""

from __future__ import annotations

from braidworks.core import Capability, OutputGroup, WeaverManifest

WEAVER_ID = "string"
WEAVER_VERSION = "0.1.0"


def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:
    """Declare every capability for the wired-in backends."""
    return WeaverManifest(
        weaver_id=WEAVER_ID,
        version=WEAVER_VERSION,
        capabilities=(
            Capability(
                id="resolve_interactions",
                consumes=frozenset({"protein.uniprot.accession"}),
                produces=frozenset(
                    {
                        "protein.interaction.count",
                        "protein.interaction.partners",
                        "protein.interaction.records",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="summary",
                        outputs=frozenset(
                            {"protein.interaction.count", "protein.interaction.partners"}
                        ),
                    ),
                    OutputGroup(id="full", outputs=frozenset({"protein.interaction.records"})),
                ),
                backends=backends,
                max_batch_size=25,
            ),
        ),
    )
