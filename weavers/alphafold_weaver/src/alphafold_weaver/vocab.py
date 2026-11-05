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

WEAVER_ID = "alphafold"
WEAVER_VERSION = "0.2.0"
WEAVER_TITLE = "AlphaFold predicted structure (accession -> model + confidence)"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://alphafold.ebi.ac.uk",
    license="CC-BY-4.0",
    citation="https://doi.org/10.1093/nar/gkab1061",
    attribution="AlphaFold DB (Google DeepMind & EMBL-EBI)",
)

# What each consumed/produced type means — from the spec's [types] table, else
# weaverkit's key registry. Lets users find fields by meaning.
TYPE_DESCRIPTIONS = {
    "protein.uniprot.accession": "UniProt accession for one protein — the main protein join key.",
    "structure.alphafold.confidence": "Observed PAE/pLDDT references with model version, coverage and metric semantics.",
    "structure.alphafold.entry_id": "This protein's AlphaFold model id.",
    "structure.alphafold.mean_plddt": "The AlphaFold model's mean pLDDT confidence, 0–100.",
    "structure.alphafold.model_coverage": "Model enumeration scope (API-only, or the archive sources scanned).",
    "structure.alphafold.model_id": "Version-qualified AlphaFold entry (entryId@vN); produced by list_models, consumed by describe_prediction.",
    "structure.alphafold.model_url": "Where to download this protein's AlphaFold model.",
    "structure.alphafold.models": "Every observed AlphaFold model of this protein, with its record.",
    "structure.alphafold.pae_image_url": "The AlphaFold model's predicted-aligned-error plot.",
    "structure.alphafold.records": "Full AlphaFold model metadata — id, confidence, URLs.",
    "structure.alphafold.version": "Which AlphaFold model version this is.",
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
                id="describe_model",
                consumes=frozenset({"protein.uniprot.accession"}),
                produces=frozenset(
                    {
                        "structure.alphafold.confidence",
                        "structure.alphafold.entry_id",
                        "structure.alphafold.mean_plddt",
                        "structure.alphafold.model_url",
                        "structure.alphafold.pae_image_url",
                        "structure.alphafold.records",
                        "structure.alphafold.version",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="model",
                        outputs=frozenset(
                            {
                                "structure.alphafold.entry_id",
                                "structure.alphafold.mean_plddt",
                                "structure.alphafold.model_url",
                                "structure.alphafold.pae_image_url",
                                "structure.alphafold.version",
                            }
                        ),
                    ),
                    OutputGroup(
                        id="confidence", outputs=frozenset({"structure.alphafold.confidence"})
                    ),
                    OutputGroup(id="full", outputs=frozenset({"structure.alphafold.records"})),
                ),
                backends=backends,
                max_batch_size=25,
            ),
            Capability(
                id="list_models",
                consumes=frozenset({"protein.uniprot.accession"}),
                produces=frozenset(
                    {
                        "structure.alphafold.model_coverage",
                        "structure.alphafold.model_id",
                        "structure.alphafold.models",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="models",
                        outputs=frozenset(
                            {
                                "structure.alphafold.model_coverage",
                                "structure.alphafold.model_id",
                                "structure.alphafold.models",
                            }
                        ),
                    ),
                ),
                backends=backends,
                max_batch_size=25,
                set_outputs=frozenset({"structure.alphafold.model_id"}),
                lists=frozenset({"structure.alphafold.models"}),
            ),
            Capability(
                id="describe_prediction",
                consumes=frozenset({"structure.alphafold.model_id"}),
                produces=frozenset(
                    {
                        "structure.alphafold.confidence",
                        "structure.alphafold.entry_id",
                        "structure.alphafold.mean_plddt",
                        "structure.alphafold.model_url",
                        "structure.alphafold.pae_image_url",
                        "structure.alphafold.records",
                        "structure.alphafold.version",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="model",
                        outputs=frozenset(
                            {
                                "structure.alphafold.entry_id",
                                "structure.alphafold.mean_plddt",
                                "structure.alphafold.model_url",
                                "structure.alphafold.pae_image_url",
                                "structure.alphafold.version",
                            }
                        ),
                    ),
                    OutputGroup(
                        id="confidence", outputs=frozenset({"structure.alphafold.confidence"})
                    ),
                    OutputGroup(id="full", outputs=frozenset({"structure.alphafold.records"})),
                ),
                backends=backends,
                max_batch_size=25,
            ),
        ),
    )
