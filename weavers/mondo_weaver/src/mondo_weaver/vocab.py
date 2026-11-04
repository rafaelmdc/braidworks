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

WEAVER_ID = "mondo"
WEAVER_VERSION = "0.2.10"
WEAVER_TITLE = (
    "MONDO disease ontology (MeSH/MedDRA id or disease name -> unified MONDO id + is-a ancestors)"
)

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://mondo.monarchinitiative.org",
    license="CC-BY-4.0",
    citation="https://doi.org/10.1101/2022.04.13.22273750",
    attribution="Mondo Disease Ontology (Vasilevsky et al., Monarch Initiative)",
)

# What each consumed/produced type means — from the spec's [types] table, else
# weaverkit's key registry. Lets users find fields by meaning.
TYPE_DESCRIPTIONS = {
    "disease.meddra.id": "A MedDRA id for a disease (e.g. 10009888) — an entry point for disease-ontology lookups; produced by MedDRA-coded microbe–disease datasets (Disbiome).",
    "disease.mesh.id": "A MeSH descriptor id for a disease (e.g. D003093) — an entry point for disease-ontology lookups; produced by MeSH-coded microbe–disease datasets.",
    "disease.mondo.id": "MONDO Disease Ontology id for one disease — the unified disease join key that harmonizes MeSH / MedDRA / DOID / OMIM identities.",
    "disease.name": "A disease name (e.g. 'ulcerative colitis') — a free-text entry point that resolves to a disease ontology term via label/synonym matching.",
    "disease.ontology.ancestors": "This disease's full is-a ancestor lineage in MONDO (up to the root), a list of {mondo_id, name} — the disease-hierarchy feature / similarity basis.",
    "disease.ontology.definition": "Observed MONDO definition text; absent definitions remain unknown.",
    "disease.ontology.depth": "This disease's minimum is-a distance to a MONDO root (how specific the term is).",
    "disease.ontology.external_mappings": "Release-matched typed SSSOM records and source provenance.",
    "disease.ontology.history": "MONDO current/obsolete status with observed replacement/consider targets and source release identity.",
    "disease.ontology.mapping.records": "Observed MONDO mapping relations and source evidence.",
    "disease.ontology.name": "The MONDO term name for this disease.",
    "disease.ontology.parents": "This disease's direct is-a parents in MONDO — a list of {mondo_id, name}.",
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
                id="mondo.lookup_by_mesh",
                consumes=frozenset({"disease.mesh.id"}),
                produces=frozenset(
                    {
                        "disease.mondo.id",
                        "disease.ontology.ancestors",
                        "disease.ontology.depth",
                        "disease.ontology.mapping.records",
                        "disease.ontology.name",
                        "disease.ontology.parents",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="identity",
                        outputs=frozenset(
                            {
                                "disease.mondo.id",
                                "disease.ontology.mapping.records",
                                "disease.ontology.name",
                            }
                        ),
                    ),
                    OutputGroup(
                        id="term",
                        outputs=frozenset({"disease.ontology.depth", "disease.ontology.parents"}),
                    ),
                    OutputGroup(id="ancestors", outputs=frozenset({"disease.ontology.ancestors"})),
                ),
                backends=backends,
                always_computed_groups=frozenset({"identity"}),
            ),
            Capability(
                id="mondo.lookup_by_meddra",
                consumes=frozenset({"disease.meddra.id"}),
                produces=frozenset(
                    {
                        "disease.mondo.id",
                        "disease.ontology.ancestors",
                        "disease.ontology.depth",
                        "disease.ontology.mapping.records",
                        "disease.ontology.name",
                        "disease.ontology.parents",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="identity",
                        outputs=frozenset(
                            {
                                "disease.mondo.id",
                                "disease.ontology.mapping.records",
                                "disease.ontology.name",
                            }
                        ),
                    ),
                    OutputGroup(
                        id="term",
                        outputs=frozenset({"disease.ontology.depth", "disease.ontology.parents"}),
                    ),
                    OutputGroup(id="ancestors", outputs=frozenset({"disease.ontology.ancestors"})),
                ),
                backends=backends,
                always_computed_groups=frozenset({"identity"}),
            ),
            Capability(
                id="mondo.lookup_by_name",
                consumes=frozenset({"disease.name"}),
                produces=frozenset(
                    {
                        "disease.mondo.id",
                        "disease.ontology.ancestors",
                        "disease.ontology.depth",
                        "disease.ontology.mapping.records",
                        "disease.ontology.name",
                        "disease.ontology.parents",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="identity",
                        outputs=frozenset(
                            {
                                "disease.mondo.id",
                                "disease.ontology.mapping.records",
                                "disease.ontology.name",
                            }
                        ),
                    ),
                    OutputGroup(
                        id="term",
                        outputs=frozenset({"disease.ontology.depth", "disease.ontology.parents"}),
                    ),
                    OutputGroup(id="ancestors", outputs=frozenset({"disease.ontology.ancestors"})),
                ),
                backends=backends,
                always_computed_groups=frozenset({"identity"}),
            ),
            Capability(
                id="describe_disease",
                consumes=frozenset({"disease.mondo.id"}),
                produces=frozenset(
                    {
                        "disease.ontology.ancestors",
                        "disease.ontology.definition",
                        "disease.ontology.depth",
                        "disease.ontology.external_mappings",
                        "disease.ontology.history",
                        "disease.ontology.name",
                        "disease.ontology.parents",
                    }
                ),
                output_groups=(
                    OutputGroup(id="identity", outputs=frozenset({"disease.ontology.name"})),
                    OutputGroup(
                        id="definition", outputs=frozenset({"disease.ontology.definition"})
                    ),
                    OutputGroup(id="history", outputs=frozenset({"disease.ontology.history"})),
                    OutputGroup(
                        id="term",
                        outputs=frozenset({"disease.ontology.depth", "disease.ontology.parents"}),
                    ),
                    OutputGroup(id="ancestors", outputs=frozenset({"disease.ontology.ancestors"})),
                    OutputGroup(
                        id="mappings", outputs=frozenset({"disease.ontology.external_mappings"})
                    ),
                ),
                backends=backends,
                always_computed_groups=frozenset({"identity"}),
            ),
        ),
    )
