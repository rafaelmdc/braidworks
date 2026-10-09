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

Taxon-search HTTP 400/404 is a miss. A failed /fetch request for identifiers already returned by the source is an error, including 404. Taxon IDs, page envelope and returned strain records are validated; missing phenotype measurements remain legitimate sparse data. Stable type-strain identity and bounded scan coverage follow the policy below.

Expected HTTP, JSON-decoding and explicitly validated source-data failures are returned as failure values. Cancellation and unrelated programming exceptions propagate. Existing successful output keys are preserved; consumers should handle `ERROR` separately from biological absence. Unknown extra source fields are allowed.

## Scan coverage

Both production builders default to a positive scan budget of 1,000 strains and
honor an explicitly supplied `max_strains_scanned`. Only complete exhaustion of
the taxon catalog establishes `NO_MATCH`. Reaching the budget with unexamined
strains returns `ERROR`, including the scanned count, limit and incomplete scope.
Missing strain records and broken continuation pages also return errors. The
backend fetches only the remaining budget, and its fingerprint includes the
source URL and budget so differently scoped scans cannot share cache entries.
Traits describe the selected type strain, not all strains of the species.

## Bounded API batches

Distinct scientific-name inputs share one scan per name within each batch. Up to
four independent taxonomy/pagination chains run concurrently, while each chain
retains the chunked `/fetch` endpoint (at most 100 strain IDs per request) and its
scan budget. Results preserve each original query and position, including duplicate
inputs; cancellation joins the workers before returning.

Both builders accept `max_concurrency=2` to select a different positive integer
worker limit. The HTTP hook uses a conservative project default of two requests
per second across local BacDive clients; this is not a claimed provider quota.
An executor request budget or `BRAIDWORKS_RATE_LIMITS=bacdive:api=...` overrides
that default. Concurrency and request pacing are separate controls.

### Species scope and phenotype evidence

The existing lookup accepts an unqualified binomial species name. Genus-only,
subspecies, strain and qualifier inputs return an error rather than discarding
their taxonomic scope. Strain records must echo the requested species. Complete
ID listings are deduplicated/sorted before the bounded detail scan; the smallest
matching type-strain ID is the deterministic representative.

Request `microbe.trait.records` (group `evidence`) for its strain ID, matched
taxonomy, explicit type-strain scope, complete source fields/references/units and
conflicting observations. Scalars are emitted only when observations agree;
conflicting traits are omitted with a warning and retained evidence. These are
type-strain observations, not an assertion of species-wide consensus.

## Construction and resource lifetime

Supported builder options are explicit; unknown options raise
`BackendConfigurationError`. Empty construction remains safe for discovery.
See [configuration and lifetime](../../docs/weaver-configuration.md) for provider
configuration, source selection and owned/borrowed HTTP clients. Use
`async with weaver:` or `await weaver.aclose()` after requests finish.
