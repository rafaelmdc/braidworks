# uniprot_weaver

UniProt protein identity (gene/protein query → accession + taxid + annotation) — the
**molecular hinge** of Braidworks, over the free, keyless UniProtKB REST API.

- **Source:** https://www.uniprot.org · **License:** CC BY 4.0 (UniProt Consortium; cite https://doi.org/10.1093/nar/gkac1052)
- **Consumes:** `protein.query` (a free-text gene symbol / protein name / accession — a molecular entry point).
- **Produces:** `protein.uniprot.accession` (the protein hub key every downstream molecular
  weaver — STRING, GO, PDB/AlphaFold, Reactome — joins on), `ncbi.taxon.id`, and
  descriptive fields (`protein.name`, `protein.gene`, `protein.organism`,
  `protein.function`, `protein.length`, `protein.reviewed`).

## The bridge

A UniProt entry carries its organism's **NCBI taxid**, so this weaver *produces*
`ncbi.taxon.id`. That single edge bridges the molecular layer back into the organism
layer — a protein hit flows on to `taxon_weaver` (lineage), `bacdive_weaver` (traits),
and `disbiome_weaver` (disease). UniProt is the one node that speaks both the protein
hub key and the organism hub key.

## Deterministic representative selection

**The same query always resolves to the same protein.** UniProt's default relevance
ranking is *not* stable (a bare `TP53` can return different orthologs on different
calls), so the backend imposes a fixed total order instead:

1. Prefer **reviewed (Swiss-Prot)** over unreviewed (TrEMBL).
2. Escalate the query, most-specific first: exact **accession** → exact **gene symbol**
   (`gene_exact:`) → free text.
3. Within the top page, pick by **highest annotation score, then accession ascending**.

> **Cross-species ambiguity.** A bare gene symbol matches every species' ortholog
> equally, so the representative is the *best-annotated* ortholog — **not necessarily
> the species you expect** (`TP53` → a hamster entry, not human). This is deterministic,
> not arbitrary. For a *specific* protein, query an **accession** (`P04637` → human p53,
> exact and stable) or add an organism to the term. The MVP is "best-annotated reviewed
> hit as representative", mirroring BacDive's type-strain choice; see `CONTRIBUTING.md`
> for the planned organism→proteins direction (`ncbi.taxon.id` → accessions).

```bash
make verify   # check the weaver still matches its spec (add --strict for golden)
make test     # conformance + contract + golden + backend-mapping tests
BRAIDWORKS_RUN_LIVE=1 make test   # also hit the live UniProt API (drift detector)
```

## Registering this weaver

A weaver is only reachable to the braider once its provider is registered in the
application's `WeaverFactory`. Wherever you assemble the factory:

```python
from braidworks.core import WeaverFactory
import uniprot_weaver

factory = WeaverFactory()
uniprot_weaver.register(factory)        # makes "uniprot" buildable
```
