# Uniprot source reference

Exact source outputs, coverage and implementation constraints. Start with
[the package overview](README.md) for setup and query entry points.

## Capabilities

| Capability | Input types | Output groups / expandable keys | Backends | Parameters |
|---|---|---|---|---|
| `resolve_protein` | `protein.query` | `identity`, `taxonomy`, `function` | `api` | `organism` |
| `describe_protein` | `protein.uniprot.accession` | `identity`, `sequence`, `annotations` | `api` | — |
| `map_to_accession` | `gene.ensembl.id` or `gene.hgnc.id` or `gene.ncbi.id` or `gene.symbol` or `nucleotide.insdc.accession` or `pdb.id` or `protein.ensembl.id` or `refseq.protein.id` or `string.id` | `mapping`; expands `protein.uniprot.accession` | `api` | — |
| `map_from_accession` | `protein.uniprot.accession` | `gene_ncbi_id`, `gene_ensembl_id`, `protein_ensembl_id`, `pathway_kegg_id`, `pathway_reactome_id`, `refseq_protein_id`, `orthodb_group`, `eggnog_group`, `chembl_id`, `drugbank_id`, `pdb_id`, `string_id`, `summary`; expands `chembl.id`, `drugbank.id`, `eggnog.group`, `gene.ensembl.id`, `gene.ncbi.id`, `orthodb.group`, `pathway.kegg.id`, `pathway.reactome.id`, `pdb.id`, `protein.ensembl.id`, `refseq.protein.id`, `string.id` | `api` | — |

These are the current declared capabilities. Output groups select fields computed
together; expandable keys identify related entities you can follow. See
[the spec](weaver.spec.toml) for exact output fields and parameter defaults, or
`braidworks weavers` for the installed inventory. Backend declarations do not imply
that optional local data are already configured.

## ID mapping (`map_to_accession` / `map_from_accession`)

Two directional capabilities over the async, batched UniProt **ID-mapping** service
(`rest.uniprot.org/idmapping`). UniProt accession is the hub: the API maps **into** it
(`X → UniProtKB`) or **out of** it (`UniProtKB_AC-ID → Y`).

- `map_to_accession` uses **alternative inputs** (`consumes_any`): supply *any one* of the
  supported ids and the backend picks the UniProt `from` db. It runs two jobs (reviewed
  Swiss-Prot + full UniProtKB) and orders accessions **reviewed-first**, so
  `ExpandPolicy.top()` takes the first returned accession in that order. `ALL`
  expands the distinct accessions returned by those mapping jobs; neither policy
  guarantees a canonical sequence or an exhaustive set of isoforms. Reviewed status
  describes an entry’s curation, not canonical isoform identity. See
  [UniProt’s canonical/isoform guidance](https://www.uniprot.org/help/canonical_and_isoforms).
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

Selection is deterministic for the same returned source data. UniProt's default relevance
ranking is *not* stable (a bare `TP53` can return different orthologs on different
calls), so the backend imposes a fixed total order instead:

1. Prefer **reviewed (Swiss-Prot)** over unreviewed (TrEMBL).
2. Escalate the query, most-specific first: exact **accession** → exact **gene symbol**
   (`gene_exact:`) → free text.
3. Within the top page, pick by **highest annotation score, then accession ascending**.

> **Cross-species ambiguity.** A bare gene symbol matches every species' ortholog
> equally, so the representative is the *best-annotated* ortholog — **not necessarily
> the species you expect** (the selected organism can differ from your intended species). This is deterministic,
> not arbitrary. For a *specific* protein, query an **accession** (`P04637` → human p53,
> exact) or pass `--param organism=9606` for human. Live source data can change.

This capability returns **one representative**, not all matching proteins or
isoforms. It remains a lookup: the executor's default ambiguity pause applies to
resolver candidates and does not make this representative lookup exhaustive.
Use `map_to_accession` for a set of identifier mappings. The selection basis is
reviewed-first search, annotation score, and accession tie-break; an organism
constraint narrows the search but does not promise a unique biological match.

## Develop
Run the commands from this package directory.

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

## Source response and failure handling

Search pages and projected nested fields are validated. Search HTTP 400/404 is a miss; mapping-job HTTP 400/404 remains a job failure. Submission, polling and result envelopes must contain meaningful job/result evidence and correlated input identifiers. A failed into-hub source-database job group preserves other groups. Mapping pagination repeats/excessive pages fail rather than looping forever. Broader mapping ordering/configuration/polling-budget work remains separately tracked.

Expected HTTP, JSON-decoding and explicitly validated source-data failures are returned as failure values. Cancellation and unrelated programming exceptions propagate. Existing successful output keys are preserved; consumers should handle `ERROR` separately from biological absence. Unknown extra source fields are allowed.

## Outbound mapping coverage

Each outbound target has its own output group. A cached GeneID lookup does not
satisfy a PDB lookup. Target-only requests submit only the selected target jobs.
Requesting `protein.uniprot.mapping.count` or `protein.uniprot.mapping.records`
fetches all 12 supported target databases, even when combined with one target.
The count is the number of returned mappings across those targets, not the number
of distinct biological entities. A successful empty summary emits count `0` and
records `[]`; a failed target job makes the summary an error.

Explicit accession-shaped queries only accept that accession, including unreviewed
entries; absent accessions and organism mismatches do not fall back to gene or text
search. ID-mapping outputs are distinct sorted sets across pages; mappings into
UniProt place reviewed IDs first, then sort within each review class.

`map_to_accession` also accepts taxon-scoped `string.id` through the provider's
STRING source; it never converts that identity into a free-text protein name.

## Configured Python usage

The public builder forwards `client`, `base_url` and `max_concurrency`. Inject an
application-owned client, or use `async with build_uniprot_weaver():` to close a
lazily created owned client. Direct backend composition is also supported:

```python
import asyncio
import httpx
from braidworks.core import Strand, StrandSet
from uniprot_weaver.backends.api import UniprotApiBackend
from uniprot_weaver.weaver import UniprotWeaver


async def main():
    async with httpx.AsyncClient(base_url="https://rest.uniprot.org", timeout=30) as client:
        weaver = UniprotWeaver({"api": UniprotApiBackend(client=client)})
        inputs = [StrandSet.from_strands("human-p53", [Strand("protein.query", "P04637")])]
        results = await weaver.execute_batch(
            "resolve_protein",
            inputs,
            backend="api",
            requested_outputs=frozenset({"protein.uniprot.accession"}),
        )
        print(results[0].to_json())


asyncio.run(main())
```

Direct mapping examples (network access required):

```bash
braidworks run uniprot map_to_accession --have gene.ncbi.id=7157 --want protein.uniprot.accession
braidworks run uniprot map_from_accession --have protein.uniprot.accession=P04637 --want pdb.id
```

## Construction and resource lifetime
For validated builders and client ownership, see
[shared configuration](../../docs/weaver-configuration.md).


## Mapping-job boundaries

The API backend composes a private mapping-job client for submission, polling and
paginated retrieval. Page normalization is pure: it checks requested-ID correlation
and returns distinct sorted mappings without mutating the response. Source-database
job failures affect their input group; separate target requests remain independent.
A request spanning several targets is atomic: a failed required target returns an
error rather than a partial successful result or incomplete summary count.

Polling is bounded by 60 attempts, with a one-second delay while pending; HTTP and
pacing time are additional, so this is not a 60-second wall-clock deadline. Result
pagination is bounded by 1,000 pages and rejects repeated or malformed next links.
Failures discard partial mappings. Paired reviewed/full jobs cancel and drain their
sibling on failure or cancellation before returning. Client ownership remains with
the backend or injecting caller as documented above. No public capability or
configuration changes are required.

## Exact protein description

Use `describe_protein` to drill into an existing primary accession. It returns that
entry, including unreviewed entries, without representative selection or species
substitution. Input is case-insensitive. Secondary accessions and isoform suffixes
(such as `P04637-2`) are not automatically converted to primary accessions: this
capability returns a miss for unsupported or non-primary identifiers.

| Group | Outputs | Source cost and meaning |
|---|---|---|
| `identity` | Existing accession, name, gene, organism, reviewed, taxid, function and length | Compact search projection; identity is computed internally on every call. Request an identity output to receive this group. |
| `sequence` | `protein.sequence` | Canonical entry amino-acid string. Adds the sequence field, without downloading annotation arrays. This is not an isoform collection. |
| `annotations` | `protein.annotation.records` | Full entry retrieval; preserves comments, features, references, nested evidence, entryAudit/proteinExistence where present, and observed release headers. No hidden list cap. |

The structured record retains source feature coordinates/modifiers and evidence
codes/references as supplied. The existing `protein.function` remains a compact
display summary; use annotation records when evidence matters. Valid absent
annotation categories are empty lists; unavailable optional identity fields are
omitted. Missing/invalid requested sequences produce an error. Release metadata
identifies the observed response, not a frozen content snapshot.

Annotation calls may download large responses. The full response includes sequence
bytes even if only annotations are selected, but the sequence output is emitted
only when requested. The CLI's default is all outputs; use `--want` to control cost.
Each distinct chunk of up to 25 accessions shares one bulk OR-accession search.
Pagination is capped at ten pages and rejects repeated/malformed continuations;
a failed page discards the chunk's partial data. Other chunks remain independent.
Input positions and duplicates are preserved.

```bash
braidworks run uniprot describe_protein --have protein.uniprot.accession=P04637 --want protein.sequence,protein.length
braidworks weave --have gene.ncbi.id=7157 --want protein.sequence --only uniprot
```

Complete offline Python example (the fixture's annotation arrays are explicitly
truncated observed samples; production returns the full provider entry):

```python
import asyncio
from braidworks.core import Strand, StrandSet
from uniprot_weaver.factory import build_uniprot_weaver_fixture


async def main():
    inputs = [
        StrandSet.from_strands(f"protein-{i}", [Strand("protein.uniprot.accession", accession)])
        for i, accession in enumerate(["P04637", "A0A087WT22", "Q99999"])
    ]
    async with build_uniprot_weaver_fixture() as weaver:
        results = await weaver.execute_batch(
            "describe_protein",
            inputs,
            backend="api",
            requested_outputs=frozenset({"protein.sequence", "protein.length"}),
        )
        for result in results:
            print(result.to_json())


asyncio.run(main())
```

Use `build_uniprot_weaver()` for the live service. Proteome enumeration and
isoform-specific retrieval remain separate future capabilities. The request/entry
model follows [UniProt's API documentation paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12230682/).
