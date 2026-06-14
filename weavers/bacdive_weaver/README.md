# bacdive_weaver

BacDive type-strain phenotypes — a microbe's curated type-strain traits (morphology,
physiology, growth) keyed by scientific name, over the free, keyless BacDive API. A
terminal weaver off the organism layer; chains behind `ncbi_weaver` (which produces the
scientific name) or `uniprot_weaver` (organism of a protein).

- **Source:** https://bacdive.dsmz.de · **License:** CC-BY-4.0 · **Cite:** https://doi.org/10.1093/nar/gkab961 — BacDive (DSMZ)
- **Backend:** `api` (keyless) · **Discoverable as** `bacdive`

## Capabilities

| Capability | Consumes | Produces (by group) |
|---|---|---|
| `describe_traits` | `organism.scientific_name` | **morphology:** `microbe.trait.gram_stain`, `microbe.trait.cell_shape` · **physiology:** `microbe.trait.motility`, `microbe.trait.spore_formation`, `microbe.trait.oxygen_tolerance` · **growth:** `microbe.trait.optimum_temp`, `microbe.trait.optimum_ph` |

Requesting any output computes its group; the mapper emits only the requested slice.

## Type-strain representative

BacDive describes **type strains**, not arbitrary isolates, so a species name resolves to
its type strain's curated phenotype — deterministic and the canonical reference for the
taxon. A name with no BacDive entry is a clean `NO_MATCH`.

## Use it

Once installed it is auto-discovered by the `braidworks` CLI:

```bash
braidworks run bacdive describe_traits --have organism.scientific_name="Escherichia coli"
braidworks weave --have organism.name="Escherichia coli" --want microbe.trait.gram_stain   # routed via taxon
```

From Python:

```python
from bacdive_weaver import build_bacdive_weaver

weaver = build_bacdive_weaver()        # zero-config
# In an app that wires a WeaverFactory, `bacdive_weaver.register(factory)` adds it as a provider.
```

## Develop

```bash
make verify                        # spec ↔ manifest, reachability, real fingerprints (--strict adds golden)
make test                          # conformance + contract + golden, fully offline
BRAIDWORKS_RUN_LIVE=1 make test    # also hit the live BacDive API (schema-drift detector)
```

Extend it: [CONTRIBUTING.md](CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](../../AGENTS.md).
