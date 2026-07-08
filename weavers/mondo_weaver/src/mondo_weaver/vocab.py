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
WEAVER_VERSION = "0.2.0"
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


def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:
    """Declare every capability for the wired-in backends."""
    return WeaverManifest(
        weaver_id=WEAVER_ID,
        version=WEAVER_VERSION,
        title=WEAVER_TITLE,
        provenance=PROVENANCE,
        capabilities=(
            Capability(
                id="mondo.lookup_by_mesh",
                consumes=frozenset({"disease.mesh.id"}),
                produces=frozenset(
                    {
                        "disease.mondo.id",
                        "disease.ontology.ancestors",
                        "disease.ontology.depth",
                        "disease.ontology.name",
                        "disease.ontology.parents",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="term",
                        outputs=frozenset(
                            {
                                "disease.mondo.id",
                                "disease.ontology.depth",
                                "disease.ontology.name",
                                "disease.ontology.parents",
                            }
                        ),
                    ),
                    OutputGroup(id="ancestors", outputs=frozenset({"disease.ontology.ancestors"})),
                ),
                backends=backends,
            ),
            Capability(
                id="mondo.lookup_by_meddra",
                consumes=frozenset({"disease.meddra.id"}),
                produces=frozenset(
                    {
                        "disease.mondo.id",
                        "disease.ontology.ancestors",
                        "disease.ontology.depth",
                        "disease.ontology.name",
                        "disease.ontology.parents",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="term",
                        outputs=frozenset(
                            {
                                "disease.mondo.id",
                                "disease.ontology.depth",
                                "disease.ontology.name",
                                "disease.ontology.parents",
                            }
                        ),
                    ),
                    OutputGroup(id="ancestors", outputs=frozenset({"disease.ontology.ancestors"})),
                ),
                backends=backends,
            ),
            Capability(
                id="mondo.lookup_by_name",
                consumes=frozenset({"disease.name"}),
                produces=frozenset(
                    {
                        "disease.mondo.id",
                        "disease.ontology.ancestors",
                        "disease.ontology.depth",
                        "disease.ontology.name",
                        "disease.ontology.parents",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="term",
                        outputs=frozenset(
                            {
                                "disease.mondo.id",
                                "disease.ontology.depth",
                                "disease.ontology.name",
                                "disease.ontology.parents",
                            }
                        ),
                    ),
                    OutputGroup(id="ancestors", outputs=frozenset({"disease.ontology.ancestors"})),
                ),
                backends=backends,
            ),
        ),
    )
