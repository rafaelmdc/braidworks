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

## Representative model and coverage

For the returned response, the backend prefers entry ID `AF-{accession}-F1`;
otherwise it selects the lexicographically lowest entry ID. This is a representative
selection rule, not a guarantee of full-sequence coverage or canonical isoform
identity. The records group describes only the selected entry (URLs, version and
confidence breakdown). It does not expose all returned alternatives or source
sequence ranges; full fragment/isoform coverage remains tracked in #197.

A valid UniProt accession can lack a model. Coverage depends on the provider’s
datasets and sequence exclusions; isoforms and fragments need separate inspection.
See the [AlphaFold DB FAQ](https://www.alphafold.ebi.ac.uk/faq) for current coverage.
HTTP 400/404 and a valid empty response produce `NO_MATCH`.

The API returns the current model version (`latestVersion`), which is exposed as
`structure.alphafold.version`. The same accession can yield different versions,
coordinates, confidence or available entries after a provider update. Selection is
deterministic for a fixed response, not a historical model-version pin.

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

Extend it: [CONTRIBUTING.md](https://github.com/rafaelmdc/braidworks/blob/main/weavers/alphafold_weaver/CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](https://github.com/rafaelmdc/braidworks/blob/main/AGENTS.md).

## Batch execution

The backend runs per-query lookups with at most four concurrent operations by
default, preserving one ordered result per input and per-input failures. Set
max_concurrency when constructing the API backend to lower the bound. This is a
concurrency limit, not an HTTP requests-per-second guarantee. Existing bulk
operations, where implemented, keep their batch endpoints.

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/weavers/alphafold_weaver/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.


## Source response and failure handling

Prediction responses must be lists of model objects with an entry identifier and correctly typed projected fields. An empty list remains a miss. A malformed response affects only its accession; null/blank inputs do not issue requests.

Expected HTTP, JSON-decoding and explicitly validated source-data failures are returned as failure values. Cancellation and unrelated programming exceptions propagate. Existing successful output keys are preserved; consumers should handle `ERROR` separately from biological absence. Unknown extra source fields are allowed.
