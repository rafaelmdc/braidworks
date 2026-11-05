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
WEAVER_VERSION = "0.3.0"
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

# What each consumed/produced type means — from the spec's [types] table, else
# weaverkit's key registry. Lets users find fields by meaning.
TYPE_DESCRIPTIONS = {
    "genome.accession": "NCBI genome assembly accession (GCF_/GCA_) — the genome join key.",
    "microbe.agora.artifact": "Observed local SBML structural status; release verification and remote availability remain explicit.",
    "microbe.agora.coverage": "AGORA crosswalk release and lookup scope.",
    "microbe.agora.genome_listing": "Exact model-to-assembly source associations from the pinned crosswalk.",
    "microbe.agora.reaction_listing": "Processed-model reaction repertoire with full fan and database source identity.",
    "microbe.agora.reconstruction": "One release-qualified model's source taxid/genome associations.",
    "microbe.agora.reconstruction_id": "Release-qualified AGORA reconstruction ID; list_reconstructions produces and describe_reconstruction consumes it.",
    "microbe.agora.reconstructions": "Every reconstruction record for this organism from the bundled crosswalk.",
    "microbe.metabolism.reactions": "The reaction repertoire of this organism's AGORA2 reconstruction(s) — a list of {reconstruction_id, abbreviation, subsystem, ec, kegg, rhea}.",
    "microbe.metabolism.reconstruction": "This organism's AGORA2 genome-scale metabolic reconstruction(s) — a list of {reconstruction_id, gcf_id} (the source RefSeq genome).",
    "microbe.metabolism.sbml": "The genome-scale metabolic model (AGORA2 SBML) for this microbe — a local path per reconstruction (lazily downloaded per model), the substrate for community-flux / seed-set metabolic-complementarity analysis.",
    "ncbi.taxon.id": "NCBI Taxonomy id for one organism — the main organism join key.",
    "reaction.vmh.id": "Observed VMH reaction abbreviation; produced by AGORA list_reactions and consumed by describe_reaction.",
    "reaction.vmh.record": "VMH reaction annotation and observed model membership with database provenance.",
}


def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:
    """Declare every capability for the wired-in backends."""
    return WeaverManifest(
        weaver_id=WEAVER_ID,
        version=WEAVER_VERSION,
        title=WEAVER_TITLE,
        provenance=PROVENANCE,
        type_descriptions=dict(TYPE_DESCRIPTIONS),
        capabilities=(
            Capability(
                id="describe_metabolic_reconstruction",
                consumes=frozenset({"ncbi.taxon.id"}),
                produces=frozenset(
                    {
                        "microbe.metabolism.reactions",
                        "microbe.metabolism.reconstruction",
                        "microbe.metabolism.sbml",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="core", outputs=frozenset({"microbe.metabolism.reconstruction"})
                    ),
                    OutputGroup(
                        id="reactions", outputs=frozenset({"microbe.metabolism.reactions"})
                    ),
                    OutputGroup(id="model", outputs=frozenset({"microbe.metabolism.sbml"})),
                ),
                backends=backends,
                max_batch_size=50,
            ),
            Capability(
                id="list_reconstructions",
                consumes=frozenset({"genome.accession", "ncbi.taxon.id"}),
                produces=frozenset(
                    {
                        "microbe.agora.coverage",
                        "microbe.agora.reconstruction_id",
                        "microbe.agora.reconstructions",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="reconstructions",
                        outputs=frozenset(
                            {
                                "microbe.agora.coverage",
                                "microbe.agora.reconstruction_id",
                                "microbe.agora.reconstructions",
                            }
                        ),
                    ),
                ),
                backends=backends,
                max_batch_size=50,
                set_outputs=frozenset({"microbe.agora.reconstruction_id"}),
                consumes_any=True,
                lists=frozenset({"microbe.agora.reconstructions"}),
            ),
            Capability(
                id="describe_reconstruction",
                consumes=frozenset({"microbe.agora.reconstruction_id"}),
                produces=frozenset(
                    {
                        "microbe.agora.artifact",
                        "microbe.agora.reconstruction",
                        "microbe.metabolism.reactions",
                        "microbe.metabolism.sbml",
                    }
                ),
                output_groups=(
                    OutputGroup(id="identity", outputs=frozenset({"microbe.agora.reconstruction"})),
                    OutputGroup(id="artifact", outputs=frozenset({"microbe.agora.artifact"})),
                    OutputGroup(
                        id="reactions", outputs=frozenset({"microbe.metabolism.reactions"})
                    ),
                    OutputGroup(id="model", outputs=frozenset({"microbe.metabolism.sbml"})),
                ),
                backends=backends,
                max_batch_size=50,
            ),
            Capability(
                id="list_genomes",
                consumes=frozenset({"microbe.agora.reconstruction_id"}),
                produces=frozenset({"genome.accession", "microbe.agora.genome_listing"}),
                output_groups=(
                    OutputGroup(
                        id="genomes",
                        outputs=frozenset({"genome.accession", "microbe.agora.genome_listing"}),
                    ),
                ),
                backends=backends,
                set_outputs=frozenset({"genome.accession"}),
            ),
            Capability(
                id="list_reactions",
                consumes=frozenset({"microbe.agora.reconstruction_id"}),
                produces=frozenset({"microbe.agora.reaction_listing", "reaction.vmh.id"}),
                output_groups=(
                    OutputGroup(
                        id="reactions",
                        outputs=frozenset({"microbe.agora.reaction_listing", "reaction.vmh.id"}),
                    ),
                ),
                backends=backends,
                set_outputs=frozenset({"reaction.vmh.id"}),
            ),
            Capability(
                id="describe_reaction",
                consumes=frozenset({"reaction.vmh.id"}),
                produces=frozenset({"reaction.vmh.record"}),
                output_groups=(
                    OutputGroup(id="reaction", outputs=frozenset({"reaction.vmh.record"})),
                ),
                backends=backends,
            ),
        ),
    )
