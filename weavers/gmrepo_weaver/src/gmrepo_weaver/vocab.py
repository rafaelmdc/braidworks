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

WEAVER_ID = 'gmrepo'
WEAVER_VERSION = '0.2.8'
WEAVER_TITLE = 'GMrepo gut-metagenome abundances (taxid -> prevalence + median relative abundance, global and per-phenotype)'

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url='https://gmrepo.humangut.info',
    license='Open',
    citation='https://doi.org/10.1093/nar/gkz764',
    attribution='GMrepo (Wu et al., NAR 2020)',
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
                id='gmrepo.list_abundances',
                consumes=frozenset({'ncbi.taxon.id'}),
                produces=frozenset({'microbe.abundance.associations', 'microbe.abundance.count', 'microbe.abundance.coverage', 'microbe.abundance.overview', 'microbe.abundance.phenotype_names', 'microbe.abundance.records'}),
                output_groups=(
                    OutputGroup(id='summary', outputs=frozenset({'microbe.abundance.count', 'microbe.abundance.coverage', 'microbe.abundance.overview', 'microbe.abundance.phenotype_names'})),
                    OutputGroup(id='associations', outputs=frozenset({'microbe.abundance.associations'})),
                    OutputGroup(id='full', outputs=frozenset({'microbe.abundance.records'})),
                ),
                backends=backends,
            ),
            Capability(
                id='gmrepo.sample_profiles',
                consumes=frozenset({'disease.mesh.id'}),
                produces=frozenset({'microbe.abundance.run_metadata', 'microbe.abundance.sample_profiles'}),
                output_groups=(
                    OutputGroup(id='profiles', outputs=frozenset({'microbe.abundance.sample_profiles'})),
                    OutputGroup(id='metadata', outputs=frozenset({'microbe.abundance.run_metadata'})),
                ),
                backends=backends,
            ),
        ),
    )
