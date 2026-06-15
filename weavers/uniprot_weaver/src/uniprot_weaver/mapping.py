"""The UniProt ID-mapping db tables — the single source of truth for the map_* edges.

UniProt accession is the hub. The ID-mapping API only maps **into** the hub
(``X -> UniProtKB``) or **out of** it (``UniProtKB_AC-ID -> Y``), so the two mapping
capabilities are directional:

* ``map_to_accession`` — alternative-input (``consumes_any``): any one of :data:`FROM_DB`'s
  strand types maps to ``protein.uniprot.accession``. The backend picks the UniProt
  ``from`` db from whichever input is supplied.
* ``map_from_accession`` — consumes the accession, produces any of :data:`TO_DB`'s strand
  types. The backend picks the UniProt ``to`` db from whichever output is requested.

vocab (the manifest) and the backend both read these tables, so they cannot drift.
Programmatic db names come from ``GET rest.uniprot.org/configure/idmapping/fields``.
"""

from __future__ import annotations

ACCESSION = "protein.uniprot.accession"
MAPPING_COUNT = "protein.uniprot.mapping.count"
MAPPING_RECORDS = "protein.uniprot.mapping.records"

# UniProt as a source/target db name for the accession hub itself.
UNIPROT_FROM = "UniProtKB_AC-ID"  # the hub as a *source* (out-of-hub edges)
UNIPROT_TO = "UniProtKB"  # the hub as a *target*, full (into-hub edges)
UNIPROT_TO_REVIEWED = "UniProtKB-Swiss-Prot"  # reviewed-only — the canonical accession

# strand type consumed -> UniProt `from` db (into the hub).
FROM_DB: dict[str, str] = {
    "gene.ncbi.id": "GeneID",
    "gene.ensembl.id": "Ensembl",
    "protein.ensembl.id": "Ensembl_Protein",
    "gene.symbol": "Gene_Name",
    "refseq.protein.id": "RefSeq_Protein",
    "gene.hgnc.id": "HGNC",
    "nucleotide.insdc.accession": "EMBL-GenBank-DDBJ",
    "pdb.id": "PDB",
}

# strand type produced -> UniProt `to` db (out of the hub).
TO_DB: dict[str, str] = {
    "gene.ncbi.id": "GeneID",
    "gene.ensembl.id": "Ensembl",
    "protein.ensembl.id": "Ensembl_Protein",
    "pathway.kegg.id": "KEGG",
    "pathway.reactome.id": "Reactome",
    "refseq.protein.id": "RefSeq_Protein",
    "orthodb.group": "OrthoDB",
    "eggnog.group": "eggNOG",
    "chembl.id": "ChEMBL",
    "drugbank.id": "DrugBank",
    "pdb.id": "PDB",
    "string.id": "STRING",
}

TO_ACCESSION = "map_to_accession"
FROM_ACCESSION = "map_from_accession"
