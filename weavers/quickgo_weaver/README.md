# quickgo_weaver

Gene Ontology annotations via EBI QuickGO — a molecular weaver off the protein hub, over
the free, keyless QuickGO REST API. Lists the GO terms annotated to a protein (grouped by
the three GO aspects), and drills any single term into its definition.

- **Source:** https://www.ebi.ac.uk/QuickGO · **License:** CC-BY-4.0 · **Cite:** https://doi.org/10.1093/bioinformatics/btp536 — Gene Ontology / EMBL-EBI QuickGO
- **Backend:** `api` (keyless) · **Discoverable as** `quickgo`

## Capabilities

| Capability | Input types | Output groups / expandable keys | Backends | Parameters |
|---|---|---|---|---|
| `list_go_terms` | `protein.uniprot.accession` | `aspects`, `summary`, `full`, `annotations`, `coverage`; expands `go.term` | `api` | `evidence_code`, `evidence_usage`, `qualifier`, `aspect` |
| `describe_go_term` | `go.term` | `detail`, `relations`, `hierarchy` | `api` | — |
| `list_gene_products` | `go.term` | `products`; expands `protein.uniprot.accession` | `api` | `taxon_id`, `evidence_code`, `evidence_usage` |

These are the current declared capabilities. Output groups select fields computed
together; expandable keys identify related entities you can follow. See
[the spec](weaver.spec.toml) for exact output fields and parameter defaults, or
`braidworks weavers` for the installed inventory. Backend declarations do not imply
that optional local data are already configured.

`list_go_terms` emits `go.term` as a **set output** (the fan dimension), and
`describe_go_term` consumes it — so a fanned term is drillable end-to-end.

## Dedup + deterministic ordering

QuickGO returns one row per annotation, with source evidence, qualifiers and
references. The default budget is ten pages of 200 rows per accession.
The term inventory (go.term, go.records and aspect lists) deduplicates by GO ID
and sorts by that ID. go.count is the number of distinct terms **retrieved**,
not a claim about the complete source total or positive experimental support.

Request go.annotation.records for the retrieved source rows, preserving evidence,
qualifiers, references and annotation extensions without interpretation. Two
annotations for the same term remain separate. No evidence or qualifier filtering
is applied; read those fields before using the inventory as a biological assertion.
See the [QuickGO API](https://www.ebi.ac.uk/QuickGO/api/index.html).

Request go.annotation.coverage for complete (true / false / null), pages_retrieved,
total_pages, total_annotations, observed_annotations and reason. Completeness refers
to the reported pagination for this query; it does not establish a frozen database
snapshot. A page cap or source-count mismatch makes complete false; absent page
metadata makes it unknown. Non-complete coverage also travels as a warning even
when you request only go.count or an aspect list, including CSV/TSV exports.

Deterministic ordering applies to the same returned source data. Live annotations
can change. An accession with no annotations remains a clean NO_MATCH.

## Use it

Once installed it is auto-discovered by the `braidworks` CLI:

```bash
braidworks run quickgo describe_go_term --have go.term=GO:0006915
braidworks weave --have protein.uniprot.accession=P04637 --want go.annotation.records,go.annotation.coverage --format json
braidworks weave --have protein.query=P04637 --want go.biological_process   # routed via uniprot
# fan one protein out into each GO term's definition:
braidworks weave --have protein.query=P04637 --want go.term.name --expand all
```

From Python:

```python
from quickgo_weaver import build_quickgo_weaver

weaver = build_quickgo_weaver()  # zero-config
# In an app that wires a WeaverFactory, `quickgo_weaver.register(factory)` adds it as a provider.
```

## Develop

```bash
make verify                        # spec ↔ manifest, reachability, real fingerprints (--strict adds golden)
make test                          # conformance + contract + golden, fully offline
BRAIDWORKS_RUN_LIVE=1 make test    # also hit the live QuickGO API (schema-drift detector)
```

Extend it: [CONTRIBUTING.md](https://github.com/rafaelmdc/braidworks/blob/main/weavers/quickgo_weaver/CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](https://github.com/rafaelmdc/braidworks/blob/main/AGENTS.md).

## Batch execution

Annotation queries accept up to ten distinct accessions per HTTP query and correlate
rows by the echoed geneProductId. Paging is shared, with a budget scaled by the
number of distinct accessions. Each accession retains the configured annotation
cap (max_pages times 200); capped detail is marked incomplete. Coverage includes
query_scope and source_total_annotations for the combined query, while
total_annotations is that accession's count when the complete combined response
establishes it. An unseen accession in an incomplete batch is an error rather
than a claimed biological absence. Missing/unexpected echoed IDs are errors.

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/weavers/quickgo_weaver/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.


## Source response and failure handling

Annotation/term rows and pagination metadata are validated before projection. Missing pagination metadata still means unknown coverage, with the existing exported warning. The observed empty-source convention (zero hits, current=total=0) remains a clean miss. An explicitly echoed different accession/page or unrequested term is an error. Term-detail chunk failures preserve other chunks. For legacy singleton responses without geneProductId, correlation still relies on the single requested accession; present echoes are checked.

Expected HTTP, JSON-decoding and explicitly validated source-data failures are returned as failure values. Cancellation and unrelated programming exceptions propagate. Existing successful output keys are preserved; consumers should handle `ERROR` separately from biological absence. Unknown extra source fields are allowed.

## Source identity and pagination budget

`build_quickgo_weaver(base_url=..., client=..., max_pages=10)` exposes the
backend's pagination budget. `max_pages` must be a positive integer. Fingerprints
hash the effective endpoint (including an injected client's base URL) and budget,
so a result acquired under one budget cannot satisfy a different source policy.
Endpoint credentials are not printed; an unversioned live service remains mutable.
The existing annotation coverage output still reports whether acquisition completed.

## Construction and resource lifetime

Supported builder options are explicit; unknown options raise
`BackendConfigurationError`. Empty construction remains safe for discovery.
See [configuration and lifetime](../../docs/weaver-configuration.md) for provider
configuration, source selection and owned/borrowed HTTP clients. Use
`async with weaver:` or `await weaver.aclose()` after requests finish.

Optional annotation parameters are `evidence_code` (one ECO:nnnnnnn ID),
`evidence_usage` (`exact`, default, or `descendants`), `aspect`, and provider
`qualifier`. No evidence parameter means the previous unfiltered retrieval
scope. This is filtering, not an evidence-strength ranking.

Positive term IDs/counts/aspect names now exclude annotations explicitly marked
NOT; a term with both positive and negative evidence remains in the positive
inventory. Raw `go.annotation.records` retains both, and coverage records polarity
counts and effective filters. This corrects negative evidence previously being
presented as positive membership; consumers needing all evidence should use the
raw annotation group.

Request `go.term.relations` for observed typed children and obsoletion plus source
term data. Child relation types remain distinct. Parents/replacement IDs are not
acquired or inferred. This group reuses the term response, with no additional call.
Sources: [QuickGO annotations](https://www.ebi.ac.uk/training/online/courses/goa-and-quickgo-quick-tour/what-is-quickgo/viewing-go-annotations/),
[GO annotation semantics](https://www.geneontology.org/docs/go-annotations/).

### Hierarchy and reverse annotation queries

Request `go.term.hierarchy` on `describe_go_term` for typed parents from explicit
`is_a,part_of` paths to the three GO aspect roots, the provider's ancestor list
(including self), complete term history, `replacements` and `replaces`. Replacement
`consider` suggestions are retained, never followed automatically. The existing
children-only relation group keeps its original scope. Supplementary complete/ancestor/path endpoints use bulk term chunks, correlate
source IDs/path origins, and share acquisition for repeated inputs.

`list_gene_products` consumes `go.term` and produces a full sorted set of observed
positive UniProt accessions, raw annotation evidence and `go.reverse.coverage`.
GO matching is exact; use `taxon_id` and optional ECO `evidence_code`/`evidence_usage`
filters. Source hit totals count annotations, not distinct proteins. The configured
`max_pages` bounds acquisition per multi-term batch; incomplete coverage carries a
warning and an unobserved term in an incomplete batch returns an error rather than
an unsupported no-match. Negative annotations stay in evidence and out of the fan set.
Source contracts: [QuickGO API](https://www.ebi.ac.uk/QuickGO/api/index.html).
