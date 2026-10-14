# STRING source reference

Exact source outputs, coverage and implementation constraints. Start with
[the package overview](README.md) for setup and query entry points.

## Capabilities

| Capability | Input types | Output groups / expandable keys | Backends | Parameters |
|---|---|---|---|---|
| `list_interactions` | `protein.uniprot.accession` | `summary`, `full`; expands `string.id` | `api` | `required_score`, `network_type`, `species` |

These are the current declared capabilities. Output groups select fields computed
together; expandable keys identify related entities you can follow. See
[the spec](weaver.spec.toml) for exact output fields and parameter defaults, or
`braidworks weavers` for the installed inventory. Backend declarations do not imply
that optional local data are already configured.

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

## Develop
Run the commands from this package directory.

```bash
make verify                        # spec ↔ manifest, reachability, real fingerprints (--strict adds golden)
make test                          # conformance + contract + golden, fully offline
BRAIDWORKS_RUN_LIVE=1 make test    # also hit the live STRING API (schema-drift detector)
```

Extend it: [CONTRIBUTING.md](https://github.com/rafaelmdc/braidworks/blob/main/weavers/string_weaver/CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](https://github.com/rafaelmdc/braidworks/blob/main/AGENTS.md).

## Source response and failure handling

Mapping/edge response shapes and echoed identifiers are validated. Malformed or uncorrelatable rows now produce an error for their request chunk, including nameless edges without a query identifier that were previously silently skipped. Successful mapping/partner chunks remain available. Empty lists and identifier HTTP 400/404 remain misses. 

Expected HTTP, JSON-decoding and explicitly validated source-data failures are returned as failure values. Cancellation and unrelated programming exceptions propagate. Existing successful output keys are preserved; consumers should handle `ERROR` separately from biological absence. Unknown extra source fields are allowed.

## Pinned service identity

The default API endpoint is `https://version-12-5.string-db.org/api`, whose
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

Fan-out uses `string.id`, consumed by UniProt `map_to_accession` using its
STRING mapping source. Replace routes through partner-name `protein.query` with
this identity bridge. Display names remain in `protein.interaction.partners`;
distinct IDs sharing a name remain separate. Records include source/partner IDs,
taxon, score/channel projection and all distinct observed edge evidence. Duplicate
source/target pairs count once; highest score and canonical evidence choose the
display row, with score/ID ordering. Conflicting accession-to-STRING mappings or
taxon identities return an error instead of choosing the first.

Provider input support observed at
[UniProt mapping configuration](https://rest.uniprot.org/configure/idmapping/fields).

## Construction and resource lifetime
For validated builders and client ownership, see
[shared configuration](../../docs/weaver-configuration.md).


## Bulk requests and source pacing

The backend resolves distinct accessions in chunks of 100, then retrieves distinct
STRING proteins' partners in chunks of 100. Mapping requests explicitly set
`echo_query=1`; responses are correlated by echoed identifier or a validated query index,
never by response order. Every request identifies this client as `braidworks`.

STRING [recommends one second between calls](https://en.string-db.org/help/api/).
Direct calls default to one request per second, sharing the source/backend budget
within the process. Executor request budgets and `BRAIDWORKS_RATE_LIMITS` take precedence.
This covers requests to both endpoints; it is not a distributed cross-process limiter.

The current endpoint returns **functional associations**, which can include indirect
relationships and predictions; an edge is not proof of physical binding. Network/score
parameters remain separately tracked in #219.

```python
import asyncio
from braidworks.core import Strand, StrandSet
from string_weaver import build_string_weaver

async def main():
    async with build_string_weaver(limit=10) as weaver:
        result = (await weaver.execute_batch(
            "list_interactions",
            [StrandSet.from_strands("tp53", [Strand("protein.uniprot.accession", "P04637")])],
            requested_outputs=frozenset({"protein.interaction.records", "protein.interaction.coverage"}),
            backend="api",
        ))[0]
        print(result.to_json())

asyncio.run(main())
```

Per-query parameters: `required_score` is an upstream integer threshold 0..1000
(omitted retains the provider default); `network_type` is `functional` (default)
or `physical`; `species` is an optional positive NCBI taxon constraint applied
to both bulk mapping and partner acquisition. Coverage records effective scope
and distinguishes threshold units from returned 0..1 scores. Retrieval limits
still bound the observed network; regulatory/directed networks are not added.
