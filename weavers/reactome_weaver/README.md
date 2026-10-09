# reactome_weaver

Curated biological pathways via Reactome — a molecular weaver off the protein hub, over
the free, keyless Reactome ContentService API. The systems-level "what process is it part
of" panel of the protein dossier. Lists every pathway a protein participates in, and
drills any single pathway into its detail.

- **Source:** https://reactome.org · **License:** CC0-1.0 · **Cite:** https://doi.org/10.1093/nar/gkab1028 — Reactome
- **Backend:** `api` (keyless) · **Discoverable as** `reactome`

## Capabilities

| Capability | Consumes | Produces |
|---|---|---|
| `list_pathways` | `protein.uniprot.accession` | **`pathway.reactome.id`** (⤜ fan: every distinct pathway), `pathway.reactome.names` (top N), `pathway.reactome.count` (true total), `pathway.reactome.records` |
| `describe_pathway` | `pathway.reactome.id` | `pathway.reactome.display_name`, `pathway.reactome.species`, `pathway.reactome.in_disease`, `pathway.reactome.detail` |

`list_pathways` emits `pathway.reactome.id` as a **set output** (the fan dimension), and
`describe_pathway` consumes it — so a fanned pathway is drillable end-to-end.

## Dedup + deterministic ordering

Reactome maps the accession to its pathways; the backend dedups to **distinct pathways**
(by Reactome stable id) and orders them by stable id. `count` is the true total;
`names`/`records` are the top `limit` (default 30); `pathway.reactome.id` is the full
distinct set (uncapped — the fan dimension). Same accession → same list. An accession with
no pathways (Reactome 400/404, or an empty list) is a clean `NO_MATCH`.

## Use it

Once installed it is auto-discovered by the `braidworks` CLI:

```bash
braidworks run reactome describe_pathway --have pathway.reactome.id=R-HSA-69488
braidworks weave --have protein.query=P04637 --want pathway.reactome.names   # routed via uniprot
# fan one protein out into each pathway's detail:
braidworks weave --have protein.query=P04637 --want pathway.reactome.display_name --expand all
```

From Python:

```python
from reactome_weaver import build_reactome_weaver

weaver = build_reactome_weaver()        # zero-config
# In an app that wires a WeaverFactory, `reactome_weaver.register(factory)` adds it as a provider.
```

## Develop

```bash
make verify                        # spec ↔ manifest, reachability, real fingerprints (--strict adds golden)
make test                          # conformance + contract + golden, fully offline
BRAIDWORKS_RUN_LIVE=1 make test    # also hit the live Reactome API (schema-drift detector)
```

Extend it: [CONTRIBUTING.md](https://github.com/rafaelmdc/braidworks/blob/main/weavers/reactome_weaver/CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](https://github.com/rafaelmdc/braidworks/blob/main/AGENTS.md).

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

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/weavers/reactome_weaver/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.


## Source response and failure handling

Pathway-list and detail responses must be lists of objects with stable identifiers. Malformed data becomes an error; a genuine empty pathway list remains a miss. Detail-request failures affect only that request chunk, and later chunks are still attempted.

Expected HTTP, JSON-decoding and explicitly validated source-data failures are returned as failure values. Cancellation and unrelated programming exceptions propagate. Existing successful output keys are preserved; consumers should handle `ERROR` separately from biological absence. Unknown extra source fields are allowed.

## Source identity and display policy

`build_reactome_weaver(base_url=..., client=..., limit=30)` exposes the backend's
positive integer display cap. Full fan-out identifiers and true totals retain their
existing semantics. Fingerprints hash the effective endpoint (including an injected
client's base URL) and cap. Changing either separates cached results, without
printing endpoint credentials. Configuration identity does not freeze the contents
of an unversioned live service.

## Construction and resource lifetime

Supported builder options are explicit; unknown options raise
`BackendConfigurationError`. Empty construction remains safe for discovery.
See [configuration and lifetime](../../docs/weaver-configuration.md) for provider
configuration, source selection and owned/borrowed HTTP clients. Use
`async with weaver:` or `await weaver.aclose()` after requests finish.
