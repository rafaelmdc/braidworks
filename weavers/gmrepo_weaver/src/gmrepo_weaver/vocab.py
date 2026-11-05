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

WEAVER_ID = "gmrepo"
WEAVER_VERSION = "0.3.1"
WEAVER_TITLE = "GMrepo gut-metagenome abundances (taxid -> prevalence + median relative abundance, global and per-phenotype)"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://gmrepo.humangut.info",
    license="Open",
    citation="https://doi.org/10.1093/nar/gkz764",
    attribution="GMrepo (Wu et al., NAR 2020)",
)

# What each consumed/produced type means — from the spec's [types] table, else
# weaverkit's key registry. Lets users find fields by meaning.
TYPE_DESCRIPTIONS = {
    "disease.mesh.id": "A MeSH descriptor id for a disease (e.g. D003093) — an entry point for disease-ontology lookups; produced by MeSH-coded microbe–disease datasets.",
    "metagenome.run_id": "Observed sequencing run accession; produced and consumed by GMrepo run workflows.",
    "microbe.abundance.association_count": "How many GMrepo phenotype-association rows mention this microbe (a phenotype can have several).",
    "microbe.abundance.associations": "This microbe's per-phenotype abundance signal — mesh_id, phenotype, sample count, prevalence %, and median relative abundance (GMrepo).",
    "microbe.abundance.count": "How many phenotypes this microbe has a GMrepo abundance record for (the length of microbe.abundance.phenotype_names).",
    "microbe.abundance.coverage": "GMrepo taxon association acquisition outcome and completeness.",
    "microbe.abundance.overview": "This microbe's global gut-metagenome abundance summary — percent of all samples it occurs in, its median relative abundance, and how many phenotypes it appears in (GMrepo).",
    "microbe.abundance.phenotype_listing": "Observed source MeSH phenotype identities for a taxon.",
    "microbe.abundance.phenotype_names": "The gut-metagenome phenotypes (diseases/health) this microbe is reported prevalent in (GMrepo).",
    "microbe.abundance.records": "Full GMrepo abundance rows for this microbe — the global overview plus every per-phenotype prevalence/abundance record.",
    "microbe.abundance.run": "One acquired GMrepo sequencing run, metadata and taxonomic profile evidence.",
    "microbe.abundance.run_listing": "Acquired GMrepo runs and exact metadata filters with retained-scope coverage.",
    "microbe.abundance.run_metadata": "Observed bounded GMrepo run listing metadata with selection and profile acquisition coverage.",
    "microbe.abundance.sample_profiles": "Per-run taxonomic profiles for a phenotype (GMrepo) — the sample × taxon relative-abundance matrix (run_id, ncbi_taxon_id, rank, relative_abundance) that feeds compositional co-occurrence inference (SparCC/SPIEC-EASI).",
    "ncbi.taxon.id": "NCBI Taxonomy id for one organism — the main organism join key.",
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
                id="gmrepo.list_abundances",
                consumes=frozenset({"ncbi.taxon.id"}),
                produces=frozenset(
                    {
                        "microbe.abundance.association_count",
                        "microbe.abundance.associations",
                        "microbe.abundance.count",
                        "microbe.abundance.coverage",
                        "microbe.abundance.overview",
                        "microbe.abundance.phenotype_names",
                        "microbe.abundance.records",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="summary",
                        outputs=frozenset(
                            {
                                "microbe.abundance.association_count",
                                "microbe.abundance.count",
                                "microbe.abundance.coverage",
                                "microbe.abundance.overview",
                                "microbe.abundance.phenotype_names",
                            }
                        ),
                    ),
                    OutputGroup(
                        id="associations", outputs=frozenset({"microbe.abundance.associations"})
                    ),
                    OutputGroup(id="full", outputs=frozenset({"microbe.abundance.records"})),
                ),
                backends=backends,
                totals={"microbe.abundance.phenotype_names": "microbe.abundance.count"},
            ),
            Capability(
                id="gmrepo.sample_profiles",
                consumes=frozenset({"disease.mesh.id"}),
                produces=frozenset(
                    {"microbe.abundance.run_metadata", "microbe.abundance.sample_profiles"}
                ),
                output_groups=(
                    OutputGroup(
                        id="profiles", outputs=frozenset({"microbe.abundance.sample_profiles"})
                    ),
                    OutputGroup(
                        id="metadata", outputs=frozenset({"microbe.abundance.run_metadata"})
                    ),
                ),
                backends=backends,
            ),
            Capability(
                id="gmrepo.list_runs",
                consumes=frozenset({"disease.mesh.id"}),
                produces=frozenset({"metagenome.run_id", "microbe.abundance.run_listing"}),
                output_groups=(
                    OutputGroup(
                        id="runs",
                        outputs=frozenset({"metagenome.run_id", "microbe.abundance.run_listing"}),
                    ),
                ),
                backends=backends,
                set_outputs=frozenset({"metagenome.run_id"}),
                parameters=(
                    Parameter(
                        name="country",
                        type="string",
                        enum=(),
                        default=None,
                        description="Exact country within acquired run metadata; no inferred cohort completeness",
                    ),
                    Parameter(
                        name="sex",
                        type="string",
                        enum=(),
                        default=None,
                        description="Exact provider sex label; unknown excluded",
                    ),
                    Parameter(
                        name="project_id",
                        type="string",
                        enum=(),
                        default=None,
                        description="Exact source project identifier",
                    ),
                    Parameter(
                        name="QCStatus",
                        type="int",
                        enum=(),
                        default=None,
                        description="Exact source QC status code, no reinterpretation",
                    ),
                ),
            ),
            Capability(
                id="gmrepo.describe_run",
                consumes=frozenset({"metagenome.run_id"}),
                produces=frozenset({"microbe.abundance.run"}),
                output_groups=(
                    OutputGroup(id="run", outputs=frozenset({"microbe.abundance.run"})),
                ),
                backends=backends,
            ),
            Capability(
                id="gmrepo.list_phenotypes",
                consumes=frozenset({"ncbi.taxon.id"}),
                produces=frozenset({"disease.mesh.id", "microbe.abundance.phenotype_listing"}),
                output_groups=(
                    OutputGroup(
                        id="phenotypes",
                        outputs=frozenset(
                            {"disease.mesh.id", "microbe.abundance.phenotype_listing"}
                        ),
                    ),
                ),
                backends=backends,
                set_outputs=frozenset({"disease.mesh.id"}),
            ),
        ),
    )
