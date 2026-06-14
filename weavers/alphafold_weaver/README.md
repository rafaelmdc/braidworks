# alphafold_weaver

AlphaFold predicted 3D structure models via EBI AlphaFold DB — a **terminal** molecular
weaver off the protein hub, over the free, keyless AlphaFold DB REST API. The "what does
it look like (predicted)" panel; the companion to `pdbe_weaver` (experimental) and the
answer when no experimental structure exists.

- **Source:** https://alphafold.ebi.ac.uk · **License:** CC-BY-4.0 · **Cite:** https://doi.org/10.1093/nar/gkab1061 — AlphaFold DB (Google DeepMind & EMBL-EBI)
- **Backend:** `api` (keyless) · **Discoverable as** `alphafold`

## Capabilities

| Capability | Consumes | Produces |
|---|---|---|
| `describe_model` | `protein.uniprot.accession` | `structure.alphafold.entry_id`, `structure.alphafold.mean_plddt` (0–100 confidence), `structure.alphafold.model_url`, `structure.alphafold.pae_image_url`, `structure.alphafold.version`, `structure.alphafold.records` |

## Canonical-model pick + determinism

The endpoint returns the canonical model (`AF-{accession}-F1`) plus, for some proteins,
alternative-isoform models. The backend picks the **canonical** model (fallback: lowest
entry id), so the same accession always yields the same model. AlphaFold's coverage is
near-universal, so a *well-formed* accession almost always has a model; a malformed/
unmappable accession (HTTP 400/404) is a clean `NO_MATCH`.

## Use it

Once installed it is auto-discovered by the `braidworks` CLI:

```bash
braidworks run alphafold describe_model --have protein.uniprot.accession=P04637
braidworks weave --have protein.query=P04637 --want structure.alphafold.mean_plddt   # routed via uniprot
```

From Python:

```python
from alphafold_weaver import build_alphafold_weaver

weaver = build_alphafold_weaver()        # zero-config
# In an app that wires a WeaverFactory, `alphafold_weaver.register(factory)` adds it as a provider.
```

## Develop

```bash
make verify                        # spec ↔ manifest, reachability, real fingerprints (--strict adds golden)
make test                          # conformance + contract + golden, fully offline
BRAIDWORKS_RUN_LIVE=1 make test    # also hit the live AlphaFold API (schema-drift detector)
```

Extend it: [CONTRIBUTING.md](CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](../../AGENTS.md).
