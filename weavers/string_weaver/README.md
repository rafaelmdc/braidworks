# string_weaver

STRING protein–protein interactions — a molecular weaver off the protein hub, over the
free, keyless STRING REST API. Lists a protein's interaction partners with confidence
scores and per-evidence-channel subscores.

- **Source:** https://string-db.org · **License:** CC-BY-4.0 · **Cite:** https://doi.org/10.1093/nar/gkac1000 — STRING (Szklarczyk et al.)
- **Backend:** `api` (keyless) · **Discoverable as** `string`

## Capabilities

| Capability | Consumes | Produces |
|---|---|---|
| `list_interactions` | `protein.uniprot.accession` | **`protein.query`** (⤜ fan: each partner name), `protein.interaction.partners`, `protein.interaction.count`, `protein.interaction.records` (full edges: partner, combined score, per-channel subscores) |

STRING maps the accession to its protein + species itself, so this is single-input and
reachable directly off the hub. It emits each partner name as **`protein.query`** (a set
output) — the same key `uniprot_weaver` consumes — so fanning out re-resolves each partner
back through UniProt: `protein → partners → fan → each partner's UniProt entry`.

## Deterministic ordering

STRING returns partners ranked by confidence, but ties are not ordered stably. The backend
imposes a fixed total order — **combined score descending, then partner name ascending** —
and caps the display at `limit` (default 25). So the same accession always yields the same
partner list. An identifier STRING can't map (HTTP 400/404) is a clean `NO_MATCH`.

## Use it

Once installed it is auto-discovered by the `braidworks` CLI:

```bash
braidworks run string list_interactions --have protein.uniprot.accession=P04637
braidworks weave --have protein.query=P04637 --want protein.interaction.partners   # routed via uniprot
```

From Python:

```python
from string_weaver import build_string_weaver

weaver = build_string_weaver()        # zero-config
# In an app that wires a WeaverFactory, `string_weaver.register(factory)` adds it as a provider.
```

## Develop

```bash
make verify                        # spec ↔ manifest, reachability, real fingerprints (--strict adds golden)
make test                          # conformance + contract + golden, fully offline
BRAIDWORKS_RUN_LIVE=1 make test    # also hit the live STRING API (schema-drift detector)
```

Extend it: [CONTRIBUTING.md](https://github.com/rafaelmdc/braidworks/blob/main/weavers/string_weaver/CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](https://github.com/rafaelmdc/braidworks/blob/main/AGENTS.md).

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/weavers/string_weaver/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.


## Source response and failure handling

Mapping/edge response shapes and echoed identifiers are validated. Malformed or uncorrelatable rows now produce an error for their request chunk, including nameless edges without a query identifier that were previously silently skipped. Successful mapping/partner chunks remain available. Empty lists and identifier HTTP 400/404 remain misses. This changes one existing non-contract unit test to assert the stronger failure semantics; conformance tests are preserved.

Expected HTTP, JSON-decoding and explicitly validated source-data failures are returned as failure values. Cancellation and unrelated programming exceptions propagate. Existing successful output keys are preserved; consumers should handle `ERROR` separately from biological absence. Unknown extra source fields are allowed.
