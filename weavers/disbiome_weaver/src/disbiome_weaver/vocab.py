"""Capabilities and manifest for the weaver — generated from weaver.spec.toml.

The manifest is the machine-readable mirror of the spec; keep them in sync
(``weaverkit verify`` checks this). Edit the spec and regenerate rather than
hand-editing capabilities here.
"""

from __future__ import annotations

from braidworks.core import (
    Capability,
    OutputGroup,
    Parameter,
    Provenance,
    WeaverManifest,
)

WEAVER_ID = "disbiome"
WEAVER_VERSION = "0.3.9"
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
                id="disbiome.list_diseases",
                consumes=frozenset({"ncbi.taxon.id", "ncbi.taxon.species_id"}),
                produces=frozenset(
                    {
                        "disease.disbiome.id",
                        "disease.meddra.id",
                        "microbe.disease.associations",
                        "microbe.disease.count",
                        "microbe.disease.coverage",
                        "microbe.disease.identities",
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
                    OutputGroup(id="coverage", outputs=frozenset({"microbe.disease.coverage"})),
                    OutputGroup(
                        id="identity",
                        outputs=frozenset(
                            {
                                "disease.disbiome.id",
                                "disease.meddra.id",
                                "microbe.disease.identities",
                            }
                        ),
                    ),
                    OutputGroup(id="full", outputs=frozenset({"microbe.disease.records"})),
                ),
                backends=backends,
                set_outputs=frozenset({"disease.disbiome.id", "disease.meddra.id"}),
                consumes_any=True,
                parameters=(
                    Parameter(
                        name="sample",
                        type="string",
                        enum=(),
                        default=None,
                        description="Exact provider sample name; missing context is excluded when filtering",
                    ),
                    Parameter(
                        name="method",
                        type="string",
                        enum=(),
                        default=None,
                        description="Exact provider detection method; omitted means unfiltered",
                    ),
                    Parameter(
                        name="outcome",
                        type="string",
                        enum=(),
                        default=None,
                        description="Exact provider qualitative outcome, such as Elevated or Reduced",
                    ),
                ),
            ),
            Capability(
                id="disbiome.list_taxa",
                consumes=frozenset({"disease.disbiome.id", "disease.meddra.id"}),
                produces=frozenset({"microbe.disease.taxa", "ncbi.taxon.id"}),
                output_groups=(
                    OutputGroup(
                        id="taxa", outputs=frozenset({"microbe.disease.taxa", "ncbi.taxon.id"})
                    ),
                ),
                backends=backends,
                set_outputs=frozenset({"ncbi.taxon.id"}),
                consumes_any=True,
                parameters=(
                    Parameter(
                        name="sample",
                        type="string",
                        enum=(),
                        default=None,
                        description="Exact source sample name; missing context excluded",
                    ),
                    Parameter(
                        name="method",
                        type="string",
                        enum=(),
                        default=None,
                        description="Exact source detection method",
                    ),
                    Parameter(
                        name="outcome",
                        type="string",
                        enum=(),
                        default=None,
                        description="Exact source qualitative outcome",
                    ),
                ),
            ),
            Capability(
                id="disbiome.describe_disease",
                consumes=frozenset({"disease.disbiome.id"}),
                produces=frozenset({"disease.disbiome.record"}),
                output_groups=(
                    OutputGroup(id="disease", outputs=frozenset({"disease.disbiome.record"})),
                ),
                backends=backends,
            ),
        ),
    )
