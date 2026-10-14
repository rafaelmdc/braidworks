# PDBE source reference

Exact source outputs, coverage and implementation constraints. Start with
[the package overview](README.md) for setup and query entry points.

## Capabilities

| Capability | Input types | Output groups / expandable keys | Backends | Parameters |
|---|---|---|---|---|
| `list_structures` | `protein.uniprot.accession` | `summary`, `full`; expands `pdb.id` | `api` | — |
| `describe_structure` | `pdb.id` | `detail`, `quality`, `entities`, `assemblies`, `ligands`, `mappings`, `residues`, `coordinates` | `api` | — |

These are the current declared capabilities. Output groups select fields computed
together; expandable keys identify related entities you can follow. See
[the spec](weaver.spec.toml) for exact output fields and parameter defaults, or
`braidworks weavers` for the installed inventory. Backend declarations do not imply
that optional local data are already configured.

`list_structures` emits `pdb.id` as a **set output** (the fan dimension), and
`describe_structure` consumes it — so a fanned structure is drillable end-to-end:
`protein → list_structures → fan → describe_structure`.

## Dedup + deterministic ordering

PDBe's `best_structures` returns one row per (structure, chain), so the backend dedups
to **distinct PDB structures** (keeping the best-covering chain) and orders them
best-first — **coverage descending, then resolution ascending, then pdb_id**. `count` is
the true total distinct; `ids`/`records` are the top `limit` (default 25); `pdb.id` is the
full distinct set (uncapped — the fan dimension). Ordering is deterministic for the
same observed source data; PDBe updates can change the list, coverage or ranking. An accession
with no structures (PDBe 404, or an empty mapping) is a clean `NO_MATCH`.

## Develop
Run the commands from this package directory.

```bash
make verify                        # spec ↔ manifest, reachability, real fingerprints (--strict adds golden)
make test                          # conformance + contract + golden, fully offline
BRAIDWORKS_RUN_LIVE=1 make test    # also hit the live PDBe API (schema-drift detector)
```

Extend it: [CONTRIBUTING.md](https://github.com/rafaelmdc/braidworks/blob/main/weavers/pdbe_weaver/CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](https://github.com/rafaelmdc/braidworks/blob/main/AGENTS.md).

## Batch execution

Structure lists use the observed bulk POST mappings/best_structures endpoint,
chunking at 100 distinct accessions and mapping responses back by accession.
Duplicates retain their original input positions; a missing accession is a miss,
never another accession's rows. Structure descriptions retain the bulk summary
endpoint. A single distinct accession uses the existing GET endpoint.

## Source response and failure handling

Best-structure and summary responses are validated against their keyed source shape. An unexpected response identifier is an error; results are never borrowed from another identifier. Detail-request failures affect only that request chunk, and later chunks are still attempted.

Expected HTTP, JSON-decoding and explicitly validated source-data failures are returned as failure values. Cancellation and unrelated programming exceptions propagate. Existing successful output keys are preserved; consumers should handle `ERROR` separately from biological absence. Unknown extra source fields are allowed.

## Source identity and display policy

`build_pdbe_weaver(base_url=..., client=..., limit=25)` exposes the existing
backend policy. `limit` must be a positive integer and caps the displayed lists;
full fan-out identifiers and true totals keep their existing semantics. Fingerprints
hash the effective endpoint (an injected client's base URL takes precedence) and
limit, so changing either cannot reuse an incompatible cached display. Endpoint
credentials are not printed. This identifies configuration; an unversioned live
service is not a frozen data snapshot.

Equal coverage/resolution ties choose the smallest chain ID, then canonical source
evidence. Each `structure.pdb.records` entry includes the selected `chain_id`, its
original `source` row, and distinct sorted `chains` records. This preserves observed
methods and sequence ranges without adding a new capability or output group.

## Construction and resource lifetime
For validated builders and client ownership, see
[shared configuration](../../docs/weaver-configuration.md).


## Configured Python query

```python
import asyncio
from braidworks.core import Strand, StrandSet
from pdbe_weaver import build_pdbe_weaver


async def main():
    async with build_pdbe_weaver(base_url="https://www.ebi.ac.uk/pdbe/api", limit=5) as weaver:
        inputs = [StrandSet.from_strands("p53", [Strand("protein.uniprot.accession", "P04637")])]
        result = (
            await weaver.execute_batch(
                "list_structures",
                inputs,
                backend="api",
                requested_outputs=frozenset({"structure.pdb.records", "structure.pdb.count"}),
            )
        )[0]
        print(result.to_json())


asyncio.run(main())
```

The displayed records are capped at five; the count represents all distinct
structures observed in that response. Chain rows in the records retain source
entity/range evidence. Resolution and sequence coverage are useful ranking fields,
not a complete structure-quality assessment. This `list_structures` request does
not query the optional quality, assembly or ligand groups on `describe_structure`.

Full chain records include observed `ranges.uniprot` and `ranges.structure`
spans with explicit coordinate namespaces. They are not residue alignments;
structure positions do not imply author numbering. Ranking and display/fan-out
limits are unchanged.

Request `structure.pdb.quality` on `describe_structure` for the `quality` group:
bulk entry-level provider validation metrics, experimental method, source and
availability. Null or absent metrics remain unknown. The group's additional
request is skipped by default; these metrics do not define a cross-method ranking.
Source: [PDBe model quality](https://www.ebi.ac.uk/training/online/courses/exploring-pdb-entry/pdb-entry-overview/model-quality/).

### Entry detail and coordinate artifacts

`describe_structure` has independent optional `entities`, `assemblies`, `ligands`,
`mappings`, `residues` and `coordinates` groups. Entity/assembly/ligand requests use
bulk source endpoints; the single-entry UniProt mapping endpoint runs concurrently.
Provider chain IDs, structural asymmetry IDs, entity IDs, author residue numbers and
insertion codes remain distinct. Range mappings are not expanded into guessed alignments.

`structure.pdb.residues` streams the individual entry's SIFTS XML (at most 10 MiB
compressed / 50 MiB expanded). It preserves explicit residue cross-references,
unobserved-residue annotations, source database releases and artifact hash. An
oversized or malformed artifact is an error; a missing artifact stays unavailable.
[Provider SIFTS format and download paths](https://www.ebi.ac.uk/pdbe/docs/sifts/quick.html).

`coordinates` returns the provider's entry mmCIF download URL and assembly mmCIF
URLs built from observed assembly IDs. It downloads no coordinate file and makes no
claim about artifact contents. Callers can acquire selected artifacts separately.
