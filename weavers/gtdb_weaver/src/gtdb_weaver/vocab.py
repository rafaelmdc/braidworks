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

WEAVER_ID = "gtdb"
WEAVER_VERSION = "0.1.0"
WEAVER_TITLE = "GTDB genome-based taxonomy (NCBI taxid / name -> GTDB species + lineage)"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://gtdb.ecogenomic.org",
    license="CC-BY-SA-4.0",
    citation="https://doi.org/10.1093/nar/gkab776",
    attribution="GTDB (Genome Taxonomy Database), Parks et al.",
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
                id="describe_gtdb_taxonomy",
                consumes=frozenset({"ncbi.taxon.id", "organism.scientific_name"}),
                produces=frozenset({"gtdb.lineage", "gtdb.taxon.id"}),
                output_groups=(
                    OutputGroup(id="core", outputs=frozenset({"gtdb.taxon.id"})),
                    OutputGroup(id="lineage", outputs=frozenset({"gtdb.lineage"})),
                ),
                backends=backends,
                max_batch_size=50,
                consumes_any=True,
            ),
        ),
    )
