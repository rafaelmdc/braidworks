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
| `map_to_accession` | **any one of** `gene.ncbi.id`, `gene.ensembl.id`, `protein.ensembl.id`, `gene.symbol`, `refseq.protein.id`, `gene.hgnc.id`, `nucleotide.insdc.accession`, `pdb.id` | `protein.uniprot.accession` (set) + mapping count/records |
| `map_from_accession` | `protein.uniprot.accession` | **any of** `gene.ncbi.id`, `gene.ensembl.id`, `protein.ensembl.id`, `pathway.kegg.id`, `pathway.reactome.id`, `refseq.protein.id`, `orthodb.group`, `eggnog.group`, `chembl.id`, `drugbank.id`, `pdb.id`, `string.id` (each a set) + mapping count/records |

## ID mapping (`map_to_accession` / `map_from_accession`)

Two directional capabilities over the async, batched UniProt **ID-mapping** service
(`rest.uniprot.org/idmapping`). UniProt accession is the hub: the API maps **into** it
(`X → UniProtKB`) or **out of** it (`UniProtKB_AC-ID → Y`).

- `map_to_accession` uses **alternative inputs** (`consumes_any`): supply *any one* of the
  supported ids and the backend picks the UniProt `from` db. It runs two jobs (reviewed
  Swiss-Prot + full UniProtKB) and orders accessions **reviewed-first**, so
  `ExpandPolicy.top()` takes the canonical entry while `ALL` fans every isoform.
- `map_from_accession` picks the `to` db from **whichever output is requested**, so one
  capability serves every target — the planner routes `accession → pathway.kegg.id`,
  `accession → gene.ncbi.id` (reverse bridge), etc.

They compose through the hub automatically — e.g. `gene.ncbi.id → accession → structure`
(the ortholog→protein→structure chain) or `gene.symbol → accession → pathway.reactome.id`.
The db tables live in `src/uniprot_weaver/mapping.py`. Backed by the same UniProt source,
so it stays one weaver, one citation.

## The bridge

A UniProt entry carries its organism's NCBI taxid, so this weaver *produces*
`ncbi.taxon.id`. That single edge bridges the molecular layer back into the organism
layer — a protein hit flows on to `ncbi_weaver` (lineage), `bacdive_weaver` (traits),
and `disbiome_weaver` (disease). UniProt is the one node that speaks both hub keys.

## Deterministic representative selection

**Selection is deterministic for the same returned source data.** UniProt's default relevance
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
> exact) or pass `--param organism=9606` for human. Live source data can change.

This capability returns **one representative**, not all matching proteins or
isoforms. It remains a lookup: the executor's default ambiguity pause applies to
resolver candidates and does not make this representative lookup exhaustive.
Use `map_to_accession` for a set of identifier mappings. The selection basis is
reviewed-first search, annotation score, and accession tie-break; an organism
constraint narrows the search but does not promise a unique biological match.

## Use it

Once installed it is auto-discovered by the `braidworks` CLI:

```bash
braidworks run uniprot resolve_protein --have protein.query=P04637
braidworks weave --have protein.query=TP53 --param organism=9606 --want protein.uniprot.accession,ncbi.taxon.id
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

Extend it: [CONTRIBUTING.md](https://github.com/rafaelmdc/braidworks/blob/main/weavers/uniprot_weaver/CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](https://github.com/rafaelmdc/braidworks/blob/main/AGENTS.md).

## Batch execution

The backend runs per-query lookups with at most four concurrent operations by
default, preserving one ordered result per input and per-input failures. Set
max_concurrency when constructing the API backend to lower the bound. This is a
concurrency limit, not an HTTP requests-per-second guarantee. Existing bulk
operations, where implemented, keep their batch endpoints.

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/weavers/uniprot_weaver/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.


## Source response and failure handling

Search pages and projected nested fields are validated. Search HTTP 400/404 is a miss; mapping-job HTTP 400/404 remains a job failure. Submission, polling and result envelopes must contain meaningful job/result evidence and correlated input identifiers. A failed into-hub source-database job group preserves other groups. Mapping pagination repeats/excessive pages fail rather than looping forever. Broader mapping ordering/configuration/polling-budget work remains separately tracked.

Expected HTTP, JSON-decoding and explicitly validated source-data failures are returned as failure values. Cancellation and unrelated programming exceptions propagate. Existing successful output keys are preserved; consumers should handle `ERROR` separately from biological absence. Unknown extra source fields are allowed.
