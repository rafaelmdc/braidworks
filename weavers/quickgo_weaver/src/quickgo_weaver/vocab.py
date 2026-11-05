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

WEAVER_ID = "quickgo"
WEAVER_VERSION = "0.3.0"
WEAVER_TITLE = "Gene Ontology annotations (accession -> GO terms by aspect)"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://www.ebi.ac.uk/QuickGO",
    license="CC-BY-4.0",
    citation="https://doi.org/10.1093/bioinformatics/btp536",
    attribution="Gene Ontology / EMBL-EBI QuickGO",
)

# What each consumed/produced type means — from the spec's [types] table, else
# weaverkit's key registry. Lets users find fields by meaning.
TYPE_DESCRIPTIONS = {
    "go.annotation.coverage": "Pagination coverage, source counts and page-cap completeness.",
    "go.annotation.records": "Source annotation rows, retaining evidence, qualifiers and references.",
    "go.biological_process": "The biological processes this protein takes part in.",
    "go.cellular_component": "Where in the cell this protein acts.",
    "go.count": "How many distinct GO terms are annotated to this protein (all of them; omitted when retrieval was incomplete).",
    "go.molecular_function": "The molecular functions this protein is annotated with.",
    "go.records": "Deduplicated GO term inventory — GO id, name, aspect.",
    "go.reverse.annotations": "Observed exact-term reverse annotations, including negative evidence.",
    "go.reverse.coverage": "Bounded reverse annotation query pagination: pages retrieved, cap and why it stopped.",
    "go.term": "A Gene Ontology term id.",
    "go.term.aspect": "This GO term's aspect — molecular_function, biological_process, or cellular_component.",
    "go.term.definition": "What this GO term means.",
    "go.term.detail": "Full detail of this GO term — name, aspect, definition, synonyms.",
    "go.term.hierarchy": "Source paths, ancestors, directional replacements and term history.",
    "go.term.name": "The name of this GO term.",
    "go.term.relations": "Observed typed term children and obsoletion; parents/replacements not inferred.",
    "protein.uniprot.accession": "UniProt accession for one protein — the main protein join key.",
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
                id="list_go_terms",
                consumes=frozenset({"protein.uniprot.accession"}),
                produces=frozenset(
                    {
                        "go.annotation.coverage",
                        "go.annotation.records",
                        "go.biological_process",
                        "go.cellular_component",
                        "go.count",
                        "go.molecular_function",
                        "go.records",
                        "go.term",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="aspects",
                        outputs=frozenset(
                            {
                                "go.biological_process",
                                "go.cellular_component",
                                "go.molecular_function",
                            }
                        ),
                    ),
                    OutputGroup(id="summary", outputs=frozenset({"go.count", "go.term"})),
                    OutputGroup(id="full", outputs=frozenset({"go.records"})),
                    OutputGroup(id="annotations", outputs=frozenset({"go.annotation.records"})),
                    OutputGroup(id="coverage", outputs=frozenset({"go.annotation.coverage"})),
                ),
                backends=backends,
                max_batch_size=10,
                set_outputs=frozenset({"go.term"}),
                totals={"go.term": "go.count"},
                lists=frozenset(
                    {
                        "go.annotation.records",
                        "go.biological_process",
                        "go.cellular_component",
                        "go.molecular_function",
                        "go.records",
                    }
                ),
                parameters=(
                    Parameter(
                        name="evidence_code",
                        type="string",
                        enum=(),
                        default=None,
                        description="One ECO:nnnnnnn evidence ID; omitted preserves source retrieval scope",
                    ),
                    Parameter(
                        name="evidence_usage",
                        type="string",
                        enum=(
                            "exact",
                            "descendants",
                        ),
                        default="exact",
                        description="ECO matching mode, used only when evidence_code is supplied",
                    ),
                    Parameter(
                        name="qualifier",
                        type="string",
                        enum=(),
                        default=None,
                        description="Exact provider annotation qualifier; NOT evidence remains in raw records",
                    ),
                    Parameter(
                        name="aspect",
                        type="string",
                        enum=(
                            "molecular_function",
                            "biological_process",
                            "cellular_component",
                        ),
                        default=None,
                        description="GO aspect filter",
                    ),
                ),
            ),
            Capability(
                id="describe_go_term",
                consumes=frozenset({"go.term"}),
                produces=frozenset(
                    {
                        "go.term.aspect",
                        "go.term.definition",
                        "go.term.detail",
                        "go.term.hierarchy",
                        "go.term.name",
                        "go.term.relations",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="detail",
                        outputs=frozenset(
                            {
                                "go.term.aspect",
                                "go.term.definition",
                                "go.term.detail",
                                "go.term.name",
                            }
                        ),
                    ),
                    OutputGroup(id="relations", outputs=frozenset({"go.term.relations"})),
                    OutputGroup(id="hierarchy", outputs=frozenset({"go.term.hierarchy"})),
                ),
                backends=backends,
                max_batch_size=10,
            ),
            Capability(
                id="list_gene_products",
                consumes=frozenset({"go.term"}),
                produces=frozenset(
                    {"go.reverse.annotations", "go.reverse.coverage", "protein.uniprot.accession"}
                ),
                output_groups=(
                    OutputGroup(
                        id="products",
                        outputs=frozenset(
                            {
                                "go.reverse.annotations",
                                "go.reverse.coverage",
                                "protein.uniprot.accession",
                            }
                        ),
                    ),
                ),
                backends=backends,
                max_batch_size=10,
                set_outputs=frozenset({"protein.uniprot.accession"}),
                lists=frozenset({"go.reverse.annotations"}),
                parameters=(
                    Parameter(
                        name="taxon_id",
                        type="int",
                        enum=(),
                        default=None,
                        description="Restrict annotations to a source NCBI taxon ID",
                    ),
                    Parameter(
                        name="evidence_code",
                        type="string",
                        enum=(),
                        default=None,
                        description="ECO evidence code",
                    ),
                    Parameter(
                        name="evidence_usage",
                        type="string",
                        enum=(
                            "exact",
                            "descendants",
                        ),
                        default="exact",
                        description="ECO matching scope",
                    ),
                ),
            ),
        ),
    )
