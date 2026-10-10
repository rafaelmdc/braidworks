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

WEAVER_ID = 'agora'
WEAVER_VERSION = '0.2.8'
WEAVER_TITLE = 'AGORA2 metabolic reconstructions (NCBI taxid -> reconstruction + reaction repertoire)'

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url='https://www.vmh.life',
    license='CC-BY-NC-4.0',
    citation='https://doi.org/10.1038/s41587-022-01628-0',
    attribution='AGORA2 / Virtual Metabolic Human (VMH), Heinken et al., Nat Biotechnol 2023 (data CC BY-NC 4.0)',
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
                id='describe_metabolic_reconstruction',
                consumes=frozenset({'ncbi.taxon.id'}),
                produces=frozenset({'microbe.metabolism.reactions', 'microbe.metabolism.reconstruction', 'microbe.metabolism.sbml'}),
                output_groups=(
                    OutputGroup(id='core', outputs=frozenset({'microbe.metabolism.reconstruction'})),
                    OutputGroup(id='reactions', outputs=frozenset({'microbe.metabolism.reactions'})),
                    OutputGroup(id='model', outputs=frozenset({'microbe.metabolism.sbml'})),
                ),
                backends=backends,
                max_batch_size=50,
            ),
            Capability(
                id='list_reconstructions',
                consumes=frozenset({'ncbi.taxon.id'}),
                produces=frozenset({'microbe.agora.coverage', 'microbe.agora.reconstruction_id', 'microbe.agora.reconstructions'}),
                output_groups=(
                    OutputGroup(id='reconstructions', outputs=frozenset({'microbe.agora.coverage', 'microbe.agora.reconstruction_id', 'microbe.agora.reconstructions'})),
                ),
                backends=backends,
                max_batch_size=50,
                set_outputs=frozenset({'microbe.agora.reconstruction_id'}),
            ),
            Capability(
                id='describe_reconstruction',
                consumes=frozenset({'microbe.agora.reconstruction_id'}),
                produces=frozenset({'microbe.agora.artifact', 'microbe.agora.reconstruction', 'microbe.metabolism.reactions', 'microbe.metabolism.sbml'}),
                output_groups=(
                    OutputGroup(id='identity', outputs=frozenset({'microbe.agora.reconstruction'})),
                    OutputGroup(id='artifact', outputs=frozenset({'microbe.agora.artifact'})),
                    OutputGroup(id='reactions', outputs=frozenset({'microbe.metabolism.reactions'})),
                    OutputGroup(id='model', outputs=frozenset({'microbe.metabolism.sbml'})),
                ),
                backends=backends,
                max_batch_size=50,
            ),
        ),
    )
