# reactome_weaver

Curated biological pathways via Reactome — a **terminal** molecular weaver off the
protein hub, over the free, keyless Reactome ContentService API. The systems-level
"what process is it part of" panel of the protein dossier.

- **Source:** https://reactome.org · **License:** CC0 (Reactome; cite https://doi.org/10.1093/nar/gkab1028)
- **Consumes:** `protein.uniprot.accession` (produced by `uniprot_weaver`).
- **Produces** (descriptive leaves): `pathway.reactome.names` (top pathways),
  `pathway.reactome.count` (true total distinct), `pathway.reactome.records`
  (`{st_id, name, in_disease}`).

## Dedup + deterministic ordering

Reactome maps the accession to its pathways; the backend dedups to **distinct pathways**
(by Reactome stable id) and orders them by stable id. `count` is the true total;
`names`/`records` are the top `limit` (default 30). Same accession → same list. An
accession with no pathways (Reactome 400/404, or an empty list) is a clean `NO_MATCH`.

```bash
make verify   # check the weaver still matches its spec (add --strict for golden)
make test     # conformance + contract + golden + backend-mapping tests
BRAIDWORKS_RUN_LIVE=1 make test   # also hit the live Reactome API (drift detector)
```

```bash
make verify   # check the weaver still matches its spec
make test     # run conformance + contract + golden tests
```

## Registering this weaver

A weaver is only reachable to the braider once its provider is registered in the
application's `WeaverFactory`. Wherever you assemble the factory:

```python
from braidworks.core import WeaverFactory
import reactome_weaver

factory = WeaverFactory()
reactome_weaver.register(factory)        # makes "reactome" buildable
```
