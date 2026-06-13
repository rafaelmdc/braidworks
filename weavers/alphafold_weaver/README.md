# alphafold_weaver

AlphaFold predicted 3D structure models via EBI AlphaFold DB — a **terminal** molecular
weaver off the protein hub, over the free, keyless AlphaFold DB REST API. The "what does
it look like (predicted)" panel; the companion to `pdbe_weaver` (experimental) and the
answer when no experimental structure exists.

- **Source:** https://alphafold.ebi.ac.uk · **License:** CC BY 4.0 (AlphaFold DB / DeepMind & EBI; cite https://doi.org/10.1093/nar/gkab1061)
- **Consumes:** `protein.uniprot.accession` (produced by `uniprot_weaver`).
- **Produces** (descriptive leaves): `structure.alphafold.entry_id`,
  `structure.alphafold.mean_plddt` (0–100 confidence), `structure.alphafold.model_url`,
  `structure.alphafold.pae_image_url`, `structure.alphafold.version`, and
  `structure.alphafold.records` (full metadata incl. the pLDDT confidence breakdown).

## Canonical-model pick + determinism

The endpoint returns the canonical model (`AF-{accession}-F1`) plus, for some proteins,
alternative-isoform models. The backend picks the **canonical** model (fallback: lowest
entry id), so the same accession always yields the same model. AlphaFold's coverage is
near-universal, so a *well-formed* accession almost always has a model; a malformed/
unmappable accession (HTTP 400/404) is a clean `NO_MATCH`.

```bash
make verify   # check the weaver still matches its spec (add --strict for golden)
make test     # conformance + contract + golden + backend-mapping tests
BRAIDWORKS_RUN_LIVE=1 make test   # also hit the live AlphaFold API (drift detector)
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
import alphafold_weaver

factory = WeaverFactory()
alphafold_weaver.register(factory)        # makes "alphafold" buildable
```
