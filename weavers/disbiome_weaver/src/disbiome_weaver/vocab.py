"""Capabilities and manifest for the weaver — generated from weaver.spec.toml.

The manifest is the machine-readable mirror of the spec; keep them in sync
(``weaverkit verify`` checks this). Edit the spec and regenerate rather than
hand-editing capabilities here.
"""

from __future__ import annotations

from braidworks.core import Capability, OutputGroup, WeaverManifest

WEAVER_ID = "disbiome"
WEAVER_VERSION = "0.1.0"


def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:
    """Declare every capability for the wired-in backends."""
    return WeaverManifest(
        weaver_id=WEAVER_ID,
        version=WEAVER_VERSION,
        capabilities=(
            Capability(
                id="disbiome.resolve_diseases",
                consumes=frozenset({"ncbi.taxon.id"}),
                produces=frozenset(
                    {
                        "microbe.disease.associations",
                        "microbe.disease.count",
                        "microbe.disease.names",
                        "microbe.disease.records",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="summary",
                        outputs=frozenset({"microbe.disease.count", "microbe.disease.names"}),
                    ),
                    OutputGroup(
                        id="associations", outputs=frozenset({"microbe.disease.associations"})
                    ),
                    OutputGroup(id="full", outputs=frozenset({"microbe.disease.records"})),
                ),
                backends=backends,
            ),
        ),
    )
