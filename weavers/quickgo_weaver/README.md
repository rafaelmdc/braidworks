# quickgo_weaver

Gene Ontology annotations via EBI QuickGO — a **terminal** molecular weaver off the
protein hub, over the free, keyless QuickGO REST API.

- **Source:** https://www.ebi.ac.uk/QuickGO · **License:** CC BY 4.0 (Gene Ontology / EBI QuickGO; cite https://doi.org/10.1093/bioinformatics/btp536)
- **Consumes:** `protein.uniprot.accession` (produced by `uniprot_weaver`).
- **Produces** (descriptive leaves, grouped by GO aspect): `go.molecular_function`,
  `go.biological_process`, `go.cellular_component` (term-name lists), plus `go.count`
  and `go.records` (distinct `{go_id, name, aspect}`).

## Dedup + deterministic ordering

QuickGO returns **one row per annotation evidence**, so a single protein yields
hundreds of rows across many pages. The backend paginates (up to a page cap, default
10 × 200 = 2000 annotations — truncation is logged, not silent), **dedups to distinct
GO terms**, and sorts them by GO id. So the same accession always yields the same
lists. An accession with no annotations is a clean `NO_MATCH`.

```bash
make verify   # check the weaver still matches its spec (add --strict for golden)
make test     # conformance + contract + golden + backend-mapping tests
BRAIDWORKS_RUN_LIVE=1 make test   # also hit the live QuickGO API (drift detector)
```

## Registering this weaver

A weaver is only reachable to the braider once its provider is registered in the
application's `WeaverFactory`. Wherever you assemble the factory:

```python
from braidworks.core import WeaverFactory
import quickgo_weaver

factory = WeaverFactory()
quickgo_weaver.register(factory)        # makes "quickgo" buildable
```
