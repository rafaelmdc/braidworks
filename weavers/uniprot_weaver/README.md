# uniprot_weaver

UniProt protein identity — a free-text gene symbol / protein name / accession resolved
to a UniProt entry. The **molecular hinge** of Braidworks: it produces both the protein
hub key (`protein.uniprot.accession`, which every downstream molecular weaver joins on)
and the organism hub key (`ncbi.taxon.id`), so a protein query can flow on to structures,
pathways, interactions — and back into the organism layer. Free, keyless UniProtKB REST API.

- **Source:** https://www.uniprot.org · **License:** CC-BY-4.0 · **Cite:** https://doi.org/10.1093/nar/gkac1052 — UniProt Consortium
- **Backend:** `api` (keyless) · **Discoverable as** `uniprot`

## Capabilities

| Capability | Consumes | Produces |
|---|---|---|
| `resolve_protein` | `protein.query` | `protein.uniprot.accession`, `ncbi.taxon.id` + leaves: `protein.name`, `protein.gene`, `protein.organism`, `protein.function`, `protein.length`, `protein.reviewed` |

## The bridge

A UniProt entry carries its organism's NCBI taxid, so this weaver *produces*
`ncbi.taxon.id`. That single edge bridges the molecular layer back into the organism
layer — a protein hit flows on to `ncbi_weaver` (lineage), `bacdive_weaver` (traits),
and `disbiome_weaver` (disease). UniProt is the one node that speaks both hub keys.

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
> exact and stable) or add an organism to the term.

## Use it

Once installed it is auto-discovered by the `braidworks` CLI:

```bash
braidworks run uniprot resolve_protein --have protein.query=P04637
braidworks weave --have protein.query=P04637 --want protein.name,ncbi.taxon.id
```

From Python:

```python
from uniprot_weaver import build_uniprot_weaver

weaver = build_uniprot_weaver()        # zero-config
# In an app that wires a WeaverFactory, `uniprot_weaver.register(factory)` adds it as a provider.
```

## Develop

```bash
make verify                        # spec ↔ manifest, reachability, real fingerprints (--strict adds golden)
make test                          # conformance + contract + golden, fully offline
BRAIDWORKS_RUN_LIVE=1 make test    # also hit the live UniProt API (schema-drift detector)
```

Extend it: [CONTRIBUTING.md](CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](../../AGENTS.md).
