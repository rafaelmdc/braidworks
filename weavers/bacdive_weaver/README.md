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

Extend it: [CONTRIBUTING.md](https://github.com/rafaelmdc/braidworks/blob/main/weavers/bacdive_weaver/CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](https://github.com/rafaelmdc/braidworks/blob/main/AGENTS.md).

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/weavers/bacdive_weaver/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.


## Source response and failure handling

Taxon-search HTTP 400/404 is a miss. A failed /fetch request for identifiers already returned by the source is an error, including 404. Taxon IDs, page envelope and returned strain records are validated; missing phenotype measurements remain legitimate sparse data. The first-type-strain and scan-cap policies are unchanged and remain separate coverage/selection work.

Expected HTTP, JSON-decoding and explicitly validated source-data failures are returned as failure values. Cancellation and unrelated programming exceptions propagate. Existing successful output keys are preserved; consumers should handle `ERROR` separately from biological absence. Unknown extra source fields are allowed.
