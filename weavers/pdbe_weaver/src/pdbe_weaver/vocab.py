"""Capabilities and manifest for the weaver — generated from weaver.spec.toml.

The manifest is the machine-readable mirror of the spec; keep them in sync
(``weaverkit verify`` checks this). Edit the spec and regenerate rather than
hand-editing capabilities here.
"""

from __future__ import annotations

from braidworks.core import Capability, OutputGroup, Provenance, WeaverManifest

WEAVER_ID = "pdbe"
WEAVER_VERSION = "0.1.4"
WEAVER_TITLE = "PDB experimental structures via PDBe (accession -> structures)"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://www.ebi.ac.uk/pdbe",
    license="CC0-1.0",
    citation="https://doi.org/10.1093/nar/gkz990",
    attribution="wwPDB / EMBL-EBI PDBe",
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
                id="list_structures",
                consumes=frozenset({"protein.uniprot.accession"}),
                produces=frozenset(
                    {
                        "pdb.id",
                        "structure.pdb.count",
                        "structure.pdb.ids",
                        "structure.pdb.records",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="summary",
                        outputs=frozenset(
                            {"pdb.id", "structure.pdb.count", "structure.pdb.ids"}
                        ),
                    ),
                    OutputGroup(id="full", outputs=frozenset({"structure.pdb.records"})),
                ),
                set_outputs=frozenset({"pdb.id"}),
                backends=backends,
                max_batch_size=25,
            ),
        ),
    )
