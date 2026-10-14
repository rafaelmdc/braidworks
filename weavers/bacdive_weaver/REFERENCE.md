# Bacdive source reference

Exact source outputs, coverage and implementation constraints. Start with
[the package overview](README.md) for setup and query entry points.

## Capabilities

| Capability | Input types | Output groups / expandable keys | Backends | Parameters |
|---|---|---|---|---|
| `describe_traits` | `organism.scientific_name` | `morphology`, `physiology`, `growth`, `evidence` | `api` | — |
| `list_strains` | `organism.scientific_name` | `strains`; expands `microbe.bacdive.strain_id` | `api` | — |
| `describe_strain` | `microbe.bacdive.strain_id` | `identity`, `morphology`, `physiology`, `growth`, `evidence` | `api` | — |
| `map_to_strain` | `culture.collection.id` or `genome.accession` | `strains`; expands `microbe.bacdive.strain_id` | `api` | — |
| `map_from_strain` | `microbe.bacdive.strain_id` | `identifiers`; expands `culture.collection.id`, `genome.accession` | `api` | — |

These are the current declared capabilities. Output groups select fields computed
together; expandable keys identify related entities you can follow. See
[the spec](weaver.spec.toml) for exact output fields and parameter defaults, or
`braidworks weavers` for the installed inventory. Backend declarations do not imply
that optional local data are already configured.

Requesting any output computes its group; the mapper emits only the requested slice.

## Type-strain representative

BacDive describes **type strains**, not arbitrary isolates, so a species name resolves to
its type strain's curated phenotype — deterministic and the canonical reference for the
taxon. A name with no BacDive entry is a clean `NO_MATCH`.

## Develop
Run the commands from this package directory.

```bash
make verify                        # spec ↔ manifest, reachability, real fingerprints (--strict adds golden)
make test                          # conformance + contract + golden, fully offline
BRAIDWORKS_RUN_LIVE=1 make test    # also hit the live BacDive API (schema-drift detector)
```

Extend it: [CONTRIBUTING.md](https://github.com/rafaelmdc/braidworks/blob/main/weavers/bacdive_weaver/CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](https://github.com/rafaelmdc/braidworks/blob/main/AGENTS.md).

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
For validated builders and client ownership, see
[shared configuration](../../docs/weaver-configuration.md).


`list_strains` lists the complete observed paginated binomial strain listing as
`microbe.bacdive.strain_id`, including type and non-type strains. The registered
integer key fans into `describe_strain`, which accepts exact BacDive IDs in
100-ID chunks and preserves individual misses. `microbe.bacdive.strain` provides
taxonomy, observed type-strain flag, culture collection references and sequence
references with source context. Trait/evidence groups also work for exact strains;
conflicting observations omit the scalar and remain in evidence.

Existing `describe_traits` still selects the deterministic type-strain
representative for an unqualified binomial. Exact strain traits do not describe
every strain of the species. API v2 remains keyless; no provider SDK is needed.
Collection/genome resolution is available through `map_to_strain`; the API remains keyless.


### Culture-collection and genome bridges

`map_to_strain` accepts either `culture.collection.id` (e.g. `DSM 2801`) or
`genome.accession` and emits the full distinct `microbe.bacdive.strain_id` set.
The collection identity wins if both alternatives are present; a miss does not
fall back to a different input. Provider multiplicity is retained instead of
arbitrarily picking one strain. Single-identifier upstream requests run with
bounded concurrency and duplicate normalized inputs share a lookup.

`map_from_strain` fetches up to 100 exact strains per request and emits observed
collection identifiers and genome assembly accessions as full sets. A collection
identifier is a prefix, one space and an observed strain token. Prefix case and
whitespace normalize; numbers and leading zeros are preserved. Compact forms,
qualifiers and unrecognized fragments are not guessed as aliases: they remain in
`microbe.bacdive.identifier_evidence`. Assembly versions remain exactly as supplied;
a versionless reference does not become a guessed versioned accession. Raw
reference evidence and isolation information remain available in exact strain data.
These are many-to-many source references, not a claim that strains with the same
name or one collection reference are universally identical.
