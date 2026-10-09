# string_weaver

STRING protein–protein interactions — a molecular weaver off the protein hub, over the
free, keyless STRING REST API. Lists a protein's interaction partners with confidence
scores and per-evidence-channel subscores.

- **Source:** https://string-db.org · **License:** CC-BY-4.0 · **Cite:** https://doi.org/10.1093/nar/gkac1000 — STRING (Szklarczyk et al.)
- **Backend:** `api` (keyless) · **Discoverable as** `string`

## Capabilities

| Capability | Consumes | Produces |
|---|---|---|
| `list_interactions` | `protein.uniprot.accession` | **`string.id`** (⤜ fan: each taxon-scoped partner ID), `protein.interaction.partners`, `protein.interaction.count`, `protein.interaction.records` (full edges: partner, combined score, per-channel subscores) |

STRING maps the accession to its protein + species itself, so this is single-input and
reachable directly off the hub. It emits each partner ID as **`string.id`** (a set
output) — the same key `uniprot_weaver` consumes — so fanning out re-resolves each partner
back through UniProt: `protein → partners → fan → each partner's UniProt entry`.

## Deterministic ordering

STRING returns partners ranked by confidence, but ties are not ordered stably. The backend
imposes a fixed total order — **combined score descending, then stable STRING partner/source IDs** —
within the upstream retrieval `limit` (default 25). This limit bounds fetched
partners, not only the display. `protein.interaction.count` counts observed edges;
`string.id` fans out only over retrieved partner IDs. Neither claims to cover
the complete interaction network. Request `protein.interaction.coverage` for the
limit, observed edge/partner counts, count/fan scope and unknown completeness. Every
successful result also carries a scope warning, including scalar-only requests. An identifier STRING can't map (HTTP 400/404) is a clean `NO_MATCH`.

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

## Pinned service identity

The default API endpoint is now `https://version-12-5.string-db.org/api`, whose
version endpoint was probed and reported 12.5. STRING recommends a
[version-specific address for production](https://version5.string-db.org/help/api/).
This replaces the mutable `string-db.org/api` default previously labelled v12.

`build_string_weaver(base_url=..., client=..., limit=25)` exposes the existing
positive retrieval limit. Fingerprints hash the effective endpoint, limit and an
honest release descriptor. An injected client's base URL is the effective source;
a custom/unversioned endpoint is not automatically labelled 12.5. Endpoint
credentials are not emitted. Retrieval coverage remains explicitly bounded, as
explained above; pinning a release does not turn a capped partner list into a full
network. Existing cache entries have different fingerprints and will not be reused.

### Stable partner identities

Fan-out now uses `string.id`, consumed by UniProt `map_to_accession` using its
STRING mapping source. Replace routes through partner-name `protein.query` with
this identity bridge. Display names remain in `protein.interaction.partners`;
distinct IDs sharing a name remain separate. Records include source/partner IDs,
taxon, score/channel projection and all distinct observed edge evidence. Duplicate
source/target pairs count once; highest score and canonical evidence choose the
display row, with score/ID ordering. Conflicting accession-to-STRING mappings or
taxon identities return an error instead of choosing the first.

Provider input support observed at
[UniProt mapping configuration](https://rest.uniprot.org/configure/idmapping/fields).
