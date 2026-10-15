# Reactome source reference

Exact source outputs, coverage and implementation constraints. Start with
[the package overview](README.md) for setup and query entry points.

## Capabilities

<!-- weaverkit:capabilities:start -->
| Capability | Input types | Output groups / expandable keys | Backends | Parameters |
|---|---|---|---|---|
| `list_pathways` | `protein.uniprot.accession` | `summary`, `full`; expands `pathway.reactome.id` | `api` | — |
| `describe_pathway` | `pathway.reactome.id` | `detail`, `hierarchy`, `participants`, `evidence` | `api` | — |
| `list_reactions` | `pathway.reactome.id` | `reactions`; expands `reaction.reactome.id` | `api` | — |
| `describe_reaction` | `reaction.reactome.id` | `detail` | `api` | — |
<!-- weaverkit:capabilities:end -->

These are the current declared capabilities. Output groups select fields computed
together; expandable keys identify related entities you can follow. See
[the spec](weaver.spec.toml) for exact output fields and parameter defaults, or
`braidworks weavers` for the installed inventory. Backend declarations do not imply
that optional local data are already configured.

`list_pathways` emits `pathway.reactome.id` as a **set output** (the fan dimension), and
`describe_pathway` consumes it — so a fanned pathway is drillable end-to-end.

## Dedup + deterministic ordering

Reactome maps the accession to its pathways; the backend dedups to **distinct pathways**
(by Reactome stable id) and orders them by stable id. `count` is the true total;
`names`/`records` are the top `limit` (default 30); `pathway.reactome.id` is the full
distinct set (uncapped — the fan dimension). Same accession → same list. An accession with
no pathways (Reactome 400/404, or an empty list) is a clean `NO_MATCH`.

## Develop
Run the commands from this package directory.

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
For validated builders and client ownership, see
[shared configuration](../../docs/weaver-configuration.md).


## Listing evidence and source updates

Compact pathway records retain `species`, `is_inferred` and a `source` object containing
the observed listing row. Missing species/inference fields remain unknown; disease
membership is a separate property. Reactome includes curated and inferred orthologous
pathways; listing membership does not itself prove experimental evidence for a protein.
See the [provider's Content Service documentation](https://reactome.org/dev/content-service).

Identical duplicate stable IDs collapse; conflicting rows return a source error in either
order instead of picking the first. Sorting is deterministic for a fixed source response.
The live service can change between calls: the endpoint fingerprint identifies configuration,
not a frozen release. `releaseDate`, if present, is a source field, not proof of the whole
database release; absent release metadata is not invented. Retaining observed evidence
adds no version request or extra upstream calls.

`describe_pathway` has requested `hierarchy` (`pathway.reactome.hierarchy`) and
`participants` (`pathway.reactome.participants`) groups. Hierarchy reports direct
observed `hasEvent` children, preserving Pathway/Reaction types, without recursive
expansion or inferred parents. Absent hierarchy information stays null.

Participants use the current `/data/participants/{id}` route and preserve complex,
set and molecule types plus source reference entities. Numeric physical entity
IDs carry the observed database release; they are not portable global IDs.
Summary defaults make no expansion or release request. Single-ID participant
requests run concurrently and reuse duplicate inputs; entry summaries stay bulk.
Source: [Reactome Content Service](https://reactome.org/dev/content-service/).

### Recursive reactions and curation evidence

`list_reactions` consumes a pathway stable ID and uses the provider's recursive
`containedEvents` endpoint. It resolves numeric object references against observed
nested identities; unresolved or conflicting identities are errors. All distinct
reaction-like stable IDs form `reaction.reactome.id`; descriptive records use the
configured display `limit` with the true total retained. Pathways are excluded and
Reaction, BlackBoxEvent and the other explicit reaction-like classes stay typed.
Repeated pathway inputs share acquisition; single-pathway requests run concurrently.

Fan into `describe_reaction` for bulk-fetched reaction detail: versioned identity,
inputs/outputs, catalysts/regulation, literature, summation, review status, evidence
and inference links. `describe_pathway` has an optional `evidence` group as well.
These are source assertions, not inferred confidence scores; missing fields remain
unknown and numeric references are not treated as stable identifiers.
[ContentService contract](https://reactome.org/ContentService/).
