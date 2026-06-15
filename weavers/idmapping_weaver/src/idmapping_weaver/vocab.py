"""Capabilities and manifest for idmapping_weaver — generated from the edge table.

Every capability is one :class:`~idmapping_weaver.edges.Edge`; this module just
projects the table into a :class:`WeaverManifest`. Keep ``edges.py`` and
``weaver.spec.toml`` in sync (``weaverkit verify`` checks the manifest against the spec).
"""

from __future__ import annotations

from braidworks.core import Capability, OutputGroup, Provenance, WeaverManifest

from idmapping_weaver import edges

WEAVER_ID = "idmapping"
WEAVER_VERSION = "0.1.0"
WEAVER_TITLE = "UniProt ID mapping — cross-reference any id to/from the UniProt accession hub"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://www.uniprot.org/help/id_mapping",
    license="CC-BY-4.0",
    citation="https://doi.org/10.1093/nar/gkac1052",
    attribution="UniProt Consortium",
)


def _capability(edge: edges.Edge, backends: tuple[str, ...]) -> Capability:
    """One ID-mapping edge as a routable capability (a set-output fan on the target id)."""
    return Capability(
        id=edge.capability,
        consumes=frozenset({edge.consumes}),
        produces=frozenset({edge.produces, edges.MAPPING_COUNT, edges.MAPPING_RECORDS}),
        output_groups=(
            OutputGroup(id="mapping", outputs=frozenset({edge.produces})),
            OutputGroup(
                id="mapping_detail",
                outputs=frozenset({edges.MAPPING_COUNT, edges.MAPPING_RECORDS}),
            ),
        ),
        backends=backends,
        max_batch_size=1000,
        set_outputs=frozenset({edge.produces}),
        always_computed_groups=frozenset({"mapping"}),
    )


def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:
    """Declare every ID-mapping edge as a capability for the wired-in backends."""
    return WeaverManifest(
        weaver_id=WEAVER_ID,
        version=WEAVER_VERSION,
        title=WEAVER_TITLE,
        provenance=PROVENANCE,
        capabilities=tuple(_capability(e, backends) for e in edges.EDGES),
    )
