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
full distinct set (uncapped — the fan dimension). Same accession → same list. An accession
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
