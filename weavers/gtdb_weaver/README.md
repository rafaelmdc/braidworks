# gtdb_weaver

GTDB genome-based taxonomy (NCBI taxid / name -> GTDB species + lineage) weaver for Braidworks.

- **Source:** https://gtdb.ecogenomic.org
- **License:** CC-BY-SA-4.0 (GTDB data — share-alike; keep attribution downstream)
- **Attribution:** GTDB (Genome Taxonomy Database), Parks et al.
- **Cite:** https://doi.org/10.1093/nar/gkab776

Maps an organism — by **NCBI taxid** or **scientific name** — to its GTDB
genome-based, rank-normalized identity: `gtdb.taxon.id` (the most specific
rank-prefixed token, e.g. `s__Escherichia coli`) and `gtdb.lineage` (an ordered
list of `{rank, name}` from domain to species). The consumed inputs are alternatives
(`consumes_any`): whichever strand is present is used.

## Capabilities

| Capability | Input types | Output groups / expandable keys | Backends | Parameters |
|---|---|---|---|---|
| `describe_gtdb_taxonomy` | `ncbi.taxon.id` or `organism.scientific_name` | `core`, `lineage`, `representative` | `local`, `api` | — |
| `describe_gtdb_tree_placement` | `ncbi.taxon.id` or `organism.scientific_name` | `core` | `local` | — |
| `describe_genome` | `genome.accession` | `identity`, `quality`, `synonyms`, `history` | `api` | — |

These are the current declared capabilities. Output groups select fields computed
together; expandable keys identify related entities you can follow. See
[the spec](weaver.spec.toml) for exact output fields and parameter defaults, or
`braidworks weavers` for the installed inventory. Backend declarations do not imply
that optional local data are already configured.

## Backends

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

## Registering this weaver

The CLI discovers this installed weaver through its entry point. Python applications
can register a built instance directly in `BraidRegistry`. `WeaverFactory` registration
is optional construction support; it makes the builder available by ID, not a route.
For applications using that factory:

```python
from braidworks.core import WeaverFactory
import gtdb_weaver

factory = WeaverFactory()
gtdb_weaver.register(factory)  # makes "gtdb" buildable
```

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/weavers/gtdb_weaver/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.

## Safe local database rebuilds

Direct builders and acquisition builds stage a fresh database beside the target,
validate its query schema and publish it atomically under the existing build lock.
Successful rebuilds remove rows from older datasets; failed input, validation or
publication leaves the original database unchanged. Allow space for both databases
and close writable target connections before replacement. Keep application-owned
tables in a separate database. Explicit local builds do not enforce the large
download disk margin used by consent-gated acquisition.

## Coherent local release bundles

Default acquisition is pinned to R232, under the official
[release232/232.0 directory](https://data.gtdb.ecogenomic.org/releases/release232/232.0/),
rather than independently reading mutable `latest` metadata and trees. The small
VERSION and MD5 manifests are checked before acquisition. Both metadata archives
are verified against provider checksums; their original SHA-256 hashes and the
bundle's tree checksums are recorded in `meta.source_bundle`.

`build_gtdb_weaver(..., release="R232")` or `ensure_gtdb_db(..., release="R232")`
selects/checks an official release. Automatic tree acquisition uses the crosswalk's
persisted bundle and release-specific paths. The bound local backend rejects trees
whose checksums do not match that bundle. A checksum failure preserves an existing
database and cleans temporary downloads. Existing local generation checks remain.

Custom metadata URLs must be supplied together. They get a custom content identity
and recorded hashes; a caller's declared release is retained as a declaration,
without borrowing a separately fetched official release label. Supply explicit
matching `tree_paths` for custom/legacy crosswalks. Old crosswalks require a schema-2 rebuild for
taxonomy, but must be refreshed to obtain verified automatic tree acquisition.
Custom tree URL acquisition under an official label is rejected; prepare custom
local tree files and pass their paths explicitly. No automatic bulk download runs
at import or during an ordinary lookup.

### Crosswalk identity policy

Schema 2 retains every distinct genome classification and representative species
candidate. An NCBI taxid with competing GTDB lineages produces an error containing
the classifications/accessions for review, including during tree placement. It
does not collapse multiple classifications into an authoritative taxon identity.
Rebuild schema-1 crosswalks using `refresh=True`. Name lookup accepts a unique
classification; API search accepts exact species names only. Equal representative
hits use stable accession/canonical-evidence ordering. Unrelated hits are misses;
competing exact lineages return review evidence.

## Bounded build and tree storage (0.2.7)

Crosswalk builders consume the source iterable once, inserting chunks of at most
1,000 classifications. SQLite retains and orders source-sized data; Python no
longer retains every row in sets and dictionaries. Classification conflicts and
representative ordering are preserved. Schema 2 remains compatible.

Local tree backends retain one parent/depth entry per node and materialize only
requested root paths. Node IDs, forest order and branch lengths match the existing
root-path helpers. Public paths are detached from the retained index.

See [the measured-work report](../../docs/audits/weavers/SH-09.implementation.md)
for fixture measurements and the separate real-release measurement target.

## Construction and resource lifetime

Supported builder options are explicit; unknown options raise
`BackendConfigurationError`. Empty construction remains safe for discovery.
See [configuration and lifetime](../../docs/weaver-configuration.md) for provider
configuration, source selection and owned/borrowed HTTP clients. Use
`async with weaver:` or `await weaver.aclose()` after requests finish.

### Source validation

Reference trees must have complete valid Newick syntax, unique nonempty leaf labels and finite nonnegative branch lengths. Downloads are validated before replacement. Missing branch lengths retain the existing zero-length interpretation.

## Representative genome evidence

Request `gtdb.genome.representative` from `describe_gtdb_taxonomy` for the species
representative's source accession and crosswalk release. This identifies the GTDB
species representative, not necessarily the input strain's own assembly. Missing
representatives remain unavailable. The API backend reports only a returned row
explicitly marked representative and leaves the release unknown; it does not
guess a release or fetch another genome. Existing taxonomy and tree outputs are
unchanged. Genome-specific quality and cross-release history are supplied by
`describe_genome`, documented below.

### Genome-specific quality, synonyms and release history

`describe_genome` consumes an exact versioned `genome.accession` on the **api**
backend. It returns observed card identity, with optional genome `quality`, source
`synonyms` and cross-release `history` groups. It does not attach genome metrics to
species-name lookups. CheckM and CheckM2 stay separate and no threshold is implied.

The card may explicitly associate GCA/GCF identities; both are retained without
assuming all such accessions are interchangeable. Its endpoint supplies no current
release, so that field remains unknown. History records retain every returned release
and lineage; classification changes are not synonyms or equivalence assertions.
Absent provider synonyms remain null. Single-genome requests run with bounded
concurrency, share repeated inputs, and preserve detached results.
[Provider OpenAPI contract](https://gtdb-api.ecogenomic.org/openapi.json).
Tree placement and distance semantics are unchanged; #234 remains deferred.
