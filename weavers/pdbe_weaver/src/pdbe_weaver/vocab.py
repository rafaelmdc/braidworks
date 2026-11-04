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

WEAVER_ID = "pdbe"
WEAVER_VERSION = "0.1.15"
WEAVER_TITLE = "PDB experimental structures via PDBe (accession -> structures)"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://www.ebi.ac.uk/pdbe",
    license="CC0-1.0",
    citation="https://doi.org/10.1093/nar/gkz990",
    attribution="wwPDB / EMBL-EBI PDBe",
)

# What each consumed/produced type means — from the spec's [types] table, else
# weaverkit's key registry. Lets users find fields by meaning.
TYPE_DESCRIPTIONS = {
    "pdb.id": "A PDB / PDBe structure id.",
    "protein.uniprot.accession": "UniProt accession for one protein — the main protein join key.",
    "structure.pdb.assemblies": "Observed PDBe assemblies detail with provider identity and availability.",
    "structure.pdb.coordinates": "Observed PDBe coordinates detail with provider identity and availability.",
    "structure.pdb.count": "How many PDB structures cover this protein.",
    "structure.pdb.detail": "Full detail of one PDB structure — title, method, dates, authors.",
    "structure.pdb.entities": "Observed PDBe entities detail with provider identity and availability.",
    "structure.pdb.ids": "Experimental PDB structures of this protein.",
    "structure.pdb.ligands": "Observed PDBe ligands detail with provider identity and availability.",
    "structure.pdb.mappings": "Observed PDBe mappings detail with provider identity and availability.",
    "structure.pdb.method": "How one PDB structure was solved.",
    "structure.pdb.quality": "Observed entry-level PDBe quality metrics with method, availability and missing-value semantics.",
    "structure.pdb.records": "This protein's PDB structures — id, method, resolution, coverage.",
    "structure.pdb.release_date": "When one PDB structure was released.",
    "structure.pdb.residues": "Observed PDBe residues detail with provider identity and availability.",
    "structure.pdb.title": "The title of one PDB structure.",
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
                id="list_structures",
                consumes=frozenset({"protein.uniprot.accession"}),
                produces=frozenset(
                    {"pdb.id", "structure.pdb.count", "structure.pdb.ids", "structure.pdb.records"}
                ),
                output_groups=(
                    OutputGroup(
                        id="summary",
                        outputs=frozenset({"pdb.id", "structure.pdb.count", "structure.pdb.ids"}),
                    ),
                    OutputGroup(id="full", outputs=frozenset({"structure.pdb.records"})),
                ),
                backends=backends,
                max_batch_size=25,
                set_outputs=frozenset({"pdb.id"}),
            ),
            Capability(
                id="describe_structure",
                consumes=frozenset({"pdb.id"}),
                produces=frozenset(
                    {
                        "structure.pdb.assemblies",
                        "structure.pdb.coordinates",
                        "structure.pdb.detail",
                        "structure.pdb.entities",
                        "structure.pdb.ligands",
                        "structure.pdb.mappings",
                        "structure.pdb.method",
                        "structure.pdb.quality",
                        "structure.pdb.release_date",
                        "structure.pdb.residues",
                        "structure.pdb.title",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="detail",
                        outputs=frozenset(
                            {
                                "structure.pdb.detail",
                                "structure.pdb.method",
                                "structure.pdb.release_date",
                                "structure.pdb.title",
                            }
                        ),
                    ),
                    OutputGroup(id="quality", outputs=frozenset({"structure.pdb.quality"})),
                    OutputGroup(id="entities", outputs=frozenset({"structure.pdb.entities"})),
                    OutputGroup(id="assemblies", outputs=frozenset({"structure.pdb.assemblies"})),
                    OutputGroup(id="ligands", outputs=frozenset({"structure.pdb.ligands"})),
                    OutputGroup(id="mappings", outputs=frozenset({"structure.pdb.mappings"})),
                    OutputGroup(id="residues", outputs=frozenset({"structure.pdb.residues"})),
                    OutputGroup(id="coordinates", outputs=frozenset({"structure.pdb.coordinates"})),
                ),
                backends=backends,
                max_batch_size=25,
            ),
        ),
    )
