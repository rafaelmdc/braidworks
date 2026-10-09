# pdbe_weaver

Experimental 3D structures via EBI PDBe — a molecular weaver off the protein hub, over
the free, keyless PDBe REST API. The "what does it look like (experimentally)" panel of
the protein dossier; pairs with `alphafold_weaver` (predicted). Lists every PDB structure
covering a protein, and drills any single structure into its detail.

- **Source:** https://www.ebi.ac.uk/pdbe · **License:** CC0-1.0 · **Cite:** https://doi.org/10.1093/nar/gkz990 — wwPDB / EMBL-EBI PDBe
- **Backend:** `api` (keyless) · **Discoverable as** `pdbe`

## Capabilities

| Capability | Consumes | Produces |
|---|---|---|
| `list_structures` | `protein.uniprot.accession` | **`pdb.id`** (⤜ fan: every distinct structure), `structure.pdb.ids` (top N), `structure.pdb.count` (true total), `structure.pdb.records` |
| `describe_structure` | `pdb.id` | `structure.pdb.title`, `structure.pdb.method`, `structure.pdb.release_date`, `structure.pdb.detail` |

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

## Use it

Once installed it is auto-discovered by the `braidworks` CLI:

```bash
braidworks run pdbe describe_structure --have pdb.id=1tup
braidworks weave --have protein.query=P04637 --want structure.pdb.ids   # routed via uniprot
# fan one protein out into each structure's detail:
braidworks weave --have protein.query=P04637 --want structure.pdb.title --expand all
```

From Python:

```python
from pdbe_weaver import build_pdbe_weaver

weaver = build_pdbe_weaver()        # zero-config
# In an app that wires a WeaverFactory, `pdbe_weaver.register(factory)` adds it as a provider.
```

## Develop

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

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/weavers/pdbe_weaver/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.


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

Supported builder options are explicit; unknown options raise
`BackendConfigurationError`. Empty construction remains safe for discovery.
See [configuration and lifetime](../../docs/weaver-configuration.md) for provider
configuration, source selection and owned/borrowed HTTP clients. Use
`async with weaver:` or `await weaver.aclose()` after requests finish.

## Complete configured Python example

```python
import asyncio
from braidworks.core import Strand, StrandSet
from pdbe_weaver import build_pdbe_weaver

async def main():
    async with build_pdbe_weaver(base_url="https://www.ebi.ac.uk/pdbe/api", limit=5) as weaver:
        inputs = [StrandSet.from_strands("p53", [Strand("protein.uniprot.accession", "P04637")])]
        result = (await weaver.execute_batch(
            "list_structures", inputs, backend="api",
            requested_outputs=frozenset({"structure.pdb.records", "structure.pdb.count"}),
        ))[0]
        print(result.to_json())

asyncio.run(main())
```

The displayed records are capped at five; the count represents all distinct
structures observed in that response. Chain rows in the records retain source
entity/range evidence. Resolution and sequence coverage are useful ranking fields,
not a complete structure-quality assessment. Additional validation, assembly and
ligand services are not queried by these capabilities.
