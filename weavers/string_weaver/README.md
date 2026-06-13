# string_weaver

STRING protein–protein interactions — a **terminal** molecular weaver hanging off the
protein hub, over the free, keyless STRING REST API.

- **Source:** https://string-db.org · **License:** CC BY 4.0 (STRING; Szklarczyk et al., cite https://doi.org/10.1093/nar/gkac1000)
- **Consumes:** `protein.uniprot.accession` (produced by `uniprot_weaver` — STRING maps the
  accession to its protein + species itself, so this is single-input and reachable
  directly off the hub).
- **Produces** (descriptive leaves, no new join keys): `protein.interaction.partners`
  (partner names), `protein.interaction.count`, `protein.interaction.records` (full edges:
  partner, combined score, per-evidence-channel subscores).

## Deterministic ordering

STRING returns partners ranked by confidence, but ties are not ordered stably. The
backend imposes a fixed total order — **combined score descending, then partner name
ascending** — and caps at `limit` (default 25). So the same accession always yields the
same partner list. An identifier STRING can't map (HTTP 400/404) is a clean `NO_MATCH`,
not an error.

```bash
make verify   # check the weaver still matches its spec (add --strict for golden)
make test     # conformance + contract + golden + backend-mapping tests
BRAIDWORKS_RUN_LIVE=1 make test   # also hit the live STRING API (drift detector)
```

## Registering this weaver

A weaver is only reachable to the braider once its provider is registered in the
application's `WeaverFactory`. Wherever you assemble the factory:

```python
from braidworks.core import WeaverFactory
import string_weaver

factory = WeaverFactory()
string_weaver.register(factory)        # makes "string" buildable
```
