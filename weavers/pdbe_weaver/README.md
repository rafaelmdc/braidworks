# pdbe_weaver

Experimental 3D structures via EBI PDBe — a **terminal** molecular weaver off the
protein hub, over the free, keyless PDBe REST API. The "what does it look like
(experimentally)" panel of the protein dossier; pairs with `alphafold_weaver` (predicted).

- **Source:** https://www.ebi.ac.uk/pdbe · **License:** CC0 (wwPDB / EBI PDBe; cite https://doi.org/10.1093/nar/gkz990)
- **Consumes:** `protein.uniprot.accession` (produced by `uniprot_weaver`).
- **Produces** (descriptive leaves): `structure.pdb.ids` (top structures, best first),
  `structure.pdb.count` (total distinct), `structure.pdb.records`
  (`{pdb_id, method, resolution, coverage}`).

## Dedup + deterministic ordering

PDBe's `best_structures` returns one row per (structure, chain), so the backend dedups
to **distinct PDB structures** (keeping the best-covering chain) and orders them
best-first — **coverage descending, then resolution ascending, then pdb_id**. `count` is
the true total distinct; `ids`/`records` are the top `limit` (default 25). Same accession
→ same list. An accession with no structures (PDBe 404, or an empty mapping) is a clean
`NO_MATCH`.

```bash
make verify   # check the weaver still matches its spec (add --strict for golden)
make test     # conformance + contract + golden + backend-mapping tests
BRAIDWORKS_RUN_LIVE=1 make test   # also hit the live PDBe API (drift detector)
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
import pdbe_weaver

factory = WeaverFactory()
pdbe_weaver.register(factory)        # makes "pdbe" buildable
```
