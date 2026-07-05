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

## Backends

- **local** (preferred, authoritative) — a small SQLite NCBI-taxid / species-name →
  GTDB crosswalk, built by streaming the GTDB metadata TSVs (`bac120` + `ar53`) into
  `~/.cache` via `ensure_gtdb_db` (consent-gated, ~150 MB download). Resolves by taxid
  (authoritative) or GTDB species name.
- **api** (online fallback, keyless) — the live GTDB search API
  (`gtdb-api.ecogenomic.org/search/gtdb`). Name-based only; a taxid-only query is a
  miss here (use the local backend for taxids).

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

A weaver is only reachable to the braider once its provider is registered in the
application's `WeaverFactory`. Wherever you assemble the factory:

```python
from braidworks.core import WeaverFactory
import gtdb_weaver

factory = WeaverFactory()
gtdb_weaver.register(factory)        # makes "gtdb" buildable
```
