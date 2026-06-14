"""Capabilities and manifest for the weaver — generated from weaver.spec.toml.

The manifest is the machine-readable mirror of the spec; keep them in sync
(``weaverkit verify`` checks this). Edit the spec and regenerate rather than
hand-editing capabilities here.
"""

from __future__ import annotations

from braidworks.core import Capability, OutputGroup, Provenance, WeaverManifest

WEAVER_ID = "disbiome"
WEAVER_VERSION = "0.1.3"
WEAVER_TITLE = "Disbiome microbe–disease associations (taxid -> diseases + direction)"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://disbiome.ugent.be",
    license="Open",
    citation="https://doi.org/10.1186/s12866-018-1197-5",
    attribution="Disbiome (Janssens et al., 2018)",
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
