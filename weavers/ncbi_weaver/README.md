# ncbi_weaver

Resolve organism names, describe taxids, follow descendants and assemblies, or retrieve genes
and orthologs. Taxonomy and descendants support local data and the Datasets API; reviewed
history is local-only and gene/genome operations are API-only. Name resolution can preserve
ambiguity for review.

- **Source:** https://www.ncbi.nlm.nih.gov/taxonomy · **License:** Public Domain — NCBI Taxonomy
- **Backends:** `local` (SQLite, bulk) + `api` (NCBI Datasets v2, keyless) · **Discoverable as** `ncbi`

## Capabilities

| Capability | Use it to |
|---|---|
| `ncbi.resolve_name` | Resolve an organism name with reviewable candidates |
| `ncbi.describe_taxon` | Describe an exact taxid |
| `ncbi.describe_taxon_history` | Inspect local taxid history |
| `ncbi.list_children` | Follow taxonomic descendants |
| `ncbi.list_genomes` | List assemblies for a taxid |
| `ncbi.describe_genome` | Inspect an assembly accession |
| `ncbi.resolve_gene` | Resolve a gene query |
| `ncbi.describe_gene` | Describe a gene ID |
| `ncbi.list_orthologs` | List observed ortholog gene IDs |

See [source reference](REFERENCE.md#capabilities) for exact inputs, output groups, backends and parameters,
or inspect the [spec](weaver.spec.toml).

## Choose a backend

```python
from ncbi_weaver import build_ncbi_weaver

weaver = build_ncbi_weaver(enable_api=True)                  # API only — no local data, zero setup
weaver = build_ncbi_weaver(db_path="data/ncbi_taxonomy.sqlite")  # local only — prebuilt SQLite
weaver = build_ncbi_weaver(auto_setup=True)                 # build/reuse the DB in the per-user cache
weaver = build_ncbi_weaver(db_path="…", enable_api=True)    # local preferred, API fallback
```

Explicit backend selection advertises the wired backends and their supported
capabilities. Zero-argument construction declares both backends for discovery: the
API is usable, while local may be unconfigured. A declared route therefore does not
guarantee a prepared local database. Gene/genome operations remain API-only; history
is local-only; taxonomy and descendant listing support both. See [docs/database.md](https://github.com/rafaelmdc/braidworks/blob/main/docs/database.md) for the
local DB. In an app that wires a `WeaverFactory`, `ncbi_weaver.register(factory)` adds it.

## Run a query

The local backend needs a one-time DB (the `api` backend doesn't):

```bash
ncbi-weaver ensure                 # prompt, then download + build the SQLite into the user cache
ncbi-weaver ensure --yes           # non-interactive (CI/servers)

braidworks run ncbi ncbi.resolve_name --have organism.name="Homo sapiens"
braidworks weave --have organism.name="Escherichia coli" --want ncbi.taxon.id,ncbi.taxon.lineage
```

> `ncbi_weaver` is the hand-written "bring your own plumbing" reference — unlike scaffolded
> weavers it carries its own `dispatch.py`/`mapper.py`, the `taxonomy_resolver` library, and
> the `ncbi-weaver` CLI, so its `vocab.py` is **hand-maintained** (don't regenerate it).

## Setup, interpretation and contribution

Use [checkout or wheel installation](../../docs/installation.md) with core and the
sources needed for your route. From the checkout, prefix commands above with
`uv run --no-sync`; a bare command assumes the environment is activated.
Source installation does not acquire optional biological databases.

[Source reference](REFERENCE.md) retains coverage, selection, failure and resource
rules. [Builder configuration](../../docs/weaver-configuration.md) documents supported
options and ownership; close configured weavers after work completes. See
[contributing](CONTRIBUTING.md) to extend this source, and run package checks from
this package directory. Current installation does not assume package-index publication.

## Software license

The software uses [MIT](LICENSE). Provider data retain their source licenses and
attribution requirements above; the manifest data license does not license this code.
