# idmapping_weaver

The **UniProt ID-mapping hub**. Cross-references any supported identifier to/from the
UniProt accession hub — so a gene id, Ensembl id, RefSeq id, structure id, or nucleotide
accession can flow *into* the protein hub, and an accession can fan *out* to pathways,
orthology groups, drugs, and more.

UniProt accession is the hub: the ID-mapping API only maps **into** the hub
(`X → UniProtKB`) or **out of** it (`UniProtKB_AC-ID → Y`), so this weaver is hub-and-spoke
— **each capability is one typed cross-reference edge**, all sharing a single async,
batched engine.

- **Source:** https://www.uniprot.org/help/id_mapping · **License:** CC-BY-4.0 · **Cite:** https://doi.org/10.1093/nar/gkac1052 — UniProt Consortium
- **Backend:** `api` (keyless) · **Discoverable as** `idmapping`

## Capabilities (Batch A — into the hub)

Every edge consumes one id type and produces `protein.uniprot.accession` (a **set output**
/ fan dimension) plus `protein.uniprot.mapping.count` and `.records`.

| Capability | Consumes | UniProt `from` db |
|---|---|---|
| `map_geneid` | `gene.ncbi.id` | `GeneID` |
| `map_ensembl` | `gene.ensembl.id` | `Ensembl` |
| `map_ensembl_protein` | `protein.ensembl.id` | `Ensembl_Protein` |
| `map_gene_name` | `gene.symbol` | `Gene_Name` |
| `map_refseq_protein` | `refseq.protein.id` | `RefSeq_Protein` |
| `map_hgnc` | `gene.hgnc.id` | `HGNC` |
| `map_insdc` | `nucleotide.insdc.accession` | `EMBL-GenBank-DDBJ` |
| `map_pdb` | `pdb.id` | `PDB` |

## Capabilities (Batch B — out of the hub)

Each consumes `protein.uniprot.accession` and produces one target id type (a **set
output**) plus the shared `protein.uniprot.mapping.count`/`.records`.

| Capability | Produces | UniProt `to` db |
|---|---|---|
| `map_to_geneid` | `gene.ncbi.id` | `GeneID` |
| `map_to_ensembl` | `gene.ensembl.id` | `Ensembl` |
| `map_to_ensembl_protein` | `protein.ensembl.id` | `Ensembl_Protein` |
| `map_to_kegg` | `pathway.kegg.id` | `KEGG` |
| `map_to_reactome` | `pathway.reactome.id` | `Reactome` |
| `map_to_refseq_protein` | `refseq.protein.id` | `RefSeq_Protein` |

These compose through the hub — e.g. `gene.symbol → accession → pathway.reactome.id` is a
two-step braid the planner finds automatically.

*Specialty out-of-hub spokes (`accession → OrthoDB / eggNOG / ChEMBL / DrugBank / PDB /
STRING`) ship in batch C.*

## How it works

The UniProt ID-mapping endpoint is **async** (submit a job → poll status → fetch results)
*and* a **batch** endpoint (many ids per job). So one capability call resolves the whole
batch of ids in one or two jobs — never one call per id.

Into-hub edges run **two jobs concurrently** — `UniProtKB-Swiss-Prot` for the canonical
**reviewed** accession and full `UniProtKB` for ids that have no reviewed entry — and order
the result **reviewed-first**, so `ExpandPolicy.top()` takes the canonical entry while
`ALL` fans every isoform.

## The point: gene → protein, and orthologs → structures

`map_geneid` is the edge that lets the gene/ortholog layer flow into the protein hub.
Composed with `ncbi_weaver`'s `list_orthologs` (a `gene.ncbi.id` fan), it turns
*"TP53's orthologs"* into *"TP53 across species, each with its 3D structure, pathways, and
interactions"* — every ortholog gene resolves to an accession, then PDBe / AlphaFold /
STRING / Reactome / QuickGO drill off it.

## Use it

```bash
braidworks run idmapping map_geneid --have gene.ncbi.id=7157   # GeneID -> accession(s)
braidworks path --from gene.ensembl.id --to protein.uniprot.accession
```

```python
from idmapping_weaver import build_idmapping_weaver

weaver = build_idmapping_weaver()        # zero-config, keyless
# In an app that wires a WeaverFactory, `idmapping_weaver.register(factory)` adds it.
```

## Develop

```bash
make verify                        # spec ↔ manifest, reachability, real fingerprints
make test                          # conformance + golden, fully offline
BRAIDWORKS_RUN_LIVE=1 make test    # also hit the live UniProt ID-mapping API
```

Adding an edge is one line in `src/idmapping_weaver/edges.py` plus a `[[capability]]` block
in `weaver.spec.toml` (the manifest is generated from the edge table).
