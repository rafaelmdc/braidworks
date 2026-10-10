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

WEAVER_ID = 'string'
WEAVER_VERSION = '0.1.13'
WEAVER_TITLE = 'STRING protein-protein interactions (accession -> partners + scores)'

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url='https://string-db.org',
    license='CC-BY-4.0',
    citation='https://doi.org/10.1093/nar/gkac1000',
    attribution='STRING (Szklarczyk et al.)',
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
                id='list_interactions',
                consumes=frozenset({'protein.uniprot.accession'}),
                produces=frozenset({'protein.interaction.count', 'protein.interaction.coverage', 'protein.interaction.partners', 'protein.interaction.records', 'string.id'}),
                output_groups=(
                    OutputGroup(id='summary', outputs=frozenset({'protein.interaction.count', 'protein.interaction.coverage', 'protein.interaction.partners', 'string.id'})),
                    OutputGroup(id='full', outputs=frozenset({'protein.interaction.records'})),
                ),
                backends=backends,
                max_batch_size=25,
                set_outputs=frozenset({'string.id'}),
                parameters=(
                    Parameter(name='required_score', type='int', enum=(), default=None, description='Upstream confidence threshold 0..1000; omitted preserves provider default'),
                    Parameter(name='network_type', type='string', enum=('functional', 'physical', ), default='functional', description='Functional association or physical interaction network'),
                    Parameter(name='species', type='int', enum=(), default=None, description='Optional positive NCBI taxon constraint applied to mapping and partners'),
                ),
            ),
        ),
    )
