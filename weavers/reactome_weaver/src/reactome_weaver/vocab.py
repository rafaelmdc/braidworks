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

WEAVER_ID = "reactome"
WEAVER_VERSION = "0.2.0"
WEAVER_TITLE = "Reactome pathways (accession -> pathways)"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://reactome.org",
    license="CC0-1.0",
    citation="https://doi.org/10.1093/nar/gkab1028",
    attribution="Reactome",
)

# What each consumed/produced type means — from the spec's [types] table, else
# weaverkit's key registry. Lets users find fields by meaning.
TYPE_DESCRIPTIONS = {
    "pathway.reactome.count": "How many Reactome pathways this protein is in.",
    "pathway.reactome.detail": "Full detail of one Reactome pathway — name, species, disease flag, type.",
    "pathway.reactome.display_name": "The name of one Reactome pathway.",
    "pathway.reactome.evidence": "Observed Reactome curation, literature and inference assertions.",
    "pathway.reactome.hierarchy": "Direct observed hasEvent children with distinct pathway/reaction types.",
    "pathway.reactome.id": "A Reactome pathway id.",
    "pathway.reactome.in_disease": "Whether one Reactome pathway is disease-associated.",
    "pathway.reactome.names": "The Reactome pathways this protein takes part in.",
    "pathway.reactome.participants": "Typed provider participant references with numeric IDs scoped to observed release.",
    "pathway.reactome.reactions": "Recursive reaction-like event listing: every reaction, its count and source.",
    "pathway.reactome.records": "This protein's Reactome pathways — stable id, name, in-disease flag.",
    "pathway.reactome.species": "The species of one Reactome pathway.",
    "protein.uniprot.accession": "UniProt accession for one protein — the main protein join key.",
    "reaction.reactome.detail": "Source reaction participants, literature, curation and inference assertions.",
    "reaction.reactome.id": "Reactome reaction-like event stable identifier; produced by recursive pathway listing and consumed by describe_reaction.",
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
                id="list_pathways",
                consumes=frozenset({"protein.uniprot.accession"}),
                produces=frozenset(
                    {
                        "pathway.reactome.count",
                        "pathway.reactome.id",
                        "pathway.reactome.names",
                        "pathway.reactome.records",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="summary",
                        outputs=frozenset(
                            {
                                "pathway.reactome.count",
                                "pathway.reactome.id",
                                "pathway.reactome.names",
                            }
                        ),
                    ),
                    OutputGroup(id="full", outputs=frozenset({"pathway.reactome.records"})),
                ),
                backends=backends,
                max_batch_size=25,
                set_outputs=frozenset({"pathway.reactome.id"}),
                totals={"pathway.reactome.names": "pathway.reactome.count"},
                lists=frozenset({"pathway.reactome.records"}),
            ),
            Capability(
                id="describe_pathway",
                consumes=frozenset({"pathway.reactome.id"}),
                produces=frozenset(
                    {
                        "pathway.reactome.detail",
                        "pathway.reactome.display_name",
                        "pathway.reactome.evidence",
                        "pathway.reactome.hierarchy",
                        "pathway.reactome.in_disease",
                        "pathway.reactome.participants",
                        "pathway.reactome.species",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="detail",
                        outputs=frozenset(
                            {
                                "pathway.reactome.detail",
                                "pathway.reactome.display_name",
                                "pathway.reactome.in_disease",
                                "pathway.reactome.species",
                            }
                        ),
                    ),
                    OutputGroup(id="hierarchy", outputs=frozenset({"pathway.reactome.hierarchy"})),
                    OutputGroup(
                        id="participants", outputs=frozenset({"pathway.reactome.participants"})
                    ),
                    OutputGroup(id="evidence", outputs=frozenset({"pathway.reactome.evidence"})),
                ),
                backends=backends,
                max_batch_size=25,
            ),
            Capability(
                id="list_reactions",
                consumes=frozenset({"pathway.reactome.id"}),
                produces=frozenset({"pathway.reactome.reactions", "reaction.reactome.id"}),
                output_groups=(
                    OutputGroup(
                        id="reactions",
                        outputs=frozenset({"pathway.reactome.reactions", "reaction.reactome.id"}),
                    ),
                ),
                backends=backends,
                max_batch_size=25,
                set_outputs=frozenset({"reaction.reactome.id"}),
            ),
            Capability(
                id="describe_reaction",
                consumes=frozenset({"reaction.reactome.id"}),
                produces=frozenset({"reaction.reactome.detail"}),
                output_groups=(
                    OutputGroup(id="detail", outputs=frozenset({"reaction.reactome.detail"})),
                ),
                backends=backends,
                max_batch_size=25,
            ),
        ),
    )
