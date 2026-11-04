# gtdb_weaver

Find GTDB taxonomy, tree placement and genome-quality/history evidence. Local crosswalks support
taxids and species names; the API supports exact species-name taxonomy and versioned genome
accessions. Taxid crosswalks and tree placement require their local artifacts. Keep release and
tree identity with the result.

- **Source:** https://gtdb.ecogenomic.org
- **License:** CC-BY-SA-4.0 (GTDB data — share-alike; keep attribution downstream)
- **Attribution:** GTDB (Genome Taxonomy Database), Parks et al.
- **Cite:** https://doi.org/10.1093/nar/gkab776

## Capabilities

| Capability | Use it to |
|---|---|
| `describe_gtdb_taxonomy` | Retrieve observed GTDB taxon identity and lineage |
| `describe_gtdb_tree_placement` | Inspect placement in a configured local tree |
| `describe_genome` | Inspect an exact genome accession |

See [source reference](REFERENCE.md#capabilities) for exact inputs, output groups, backends and parameters,
or inspect the [spec](weaver.spec.toml).

## Choose and prepare a backend

- **local** (preferred, observed genome crosswalk) — a small SQLite NCBI-taxid / species-name →
  GTDB crosswalk, built by streaming the GTDB metadata TSVs (`bac120` + `ar53`) into
  `~/.cache` via `ensure_gtdb_db` (consent-gated, ~283 MB for R232 download). Resolves by taxid
  (unique observed classification) or GTDB species name.
- **api** (online fallback, keyless) — the live GTDB search API
  (`gtdb-api.ecogenomic.org/search/gtdb`) for exact species-name taxonomy queries.
  A taxid-only taxonomy query is a miss here (use local). The API also supports
  `describe_genome` for exact versioned genome accessions and observed quality/history.

```python
import gtdb_weaver

# local backend — builds the crosswalk on first use (needs consent / auto_setup):
weaver = gtdb_weaver.build_gtdb_weaver(auto_setup=True)

# api backend only — no local build, online name search:
weaver = gtdb_weaver.build_gtdb_weaver(enable_api=True)
```

```bash
make verify   # check the weaver still matches its spec
make test     # run conformance + contract + golden tests (offline)
BRAIDWORKS_RUN_LIVE=1 make test   # also run the live GTDB-API E2E
```

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
