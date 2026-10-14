# Disbiome source reference

Exact source outputs, coverage and implementation constraints. Start with
[the package overview](README.md) for setup and query entry points.

## Capabilities

| Capability | Input types | Output groups / expandable keys | Backends | Parameters |
|---|---|---|---|---|
| `disbiome.list_diseases` | `ncbi.taxon.id` or `ncbi.taxon.species_id` | `summary`, `associations`, `coverage`, `identity`, `full`; expands `disease.disbiome.id`, `disease.meddra.id` | `local` | `sample`, `method`, `outcome` |
| `disbiome.list_taxa` | `disease.disbiome.id` or `disease.meddra.id` | `taxa`; expands `ncbi.taxon.id` | `local` | `sample`, `method`, `outcome` |
| `disbiome.describe_disease` | `disease.disbiome.id` | `disease` | `local` | — |

These are the current declared capabilities. Output groups select fields computed
together; expandable keys identify related entities you can follow. See
[the spec](weaver.spec.toml) for exact output fields and parameter defaults, or
`braidworks weavers` for the installed inventory. Backend declarations do not imply
that optional local data are already configured.

Output slices, light → heavy (the mapper emits only the requested group):

| Group | What you get |
|---|---|
| `summary` | distinct disease names + how many records |
| `associations` | one compact row per experiment: disease, direction, method, sample, host |
| `full` | the complete joined blob — every experiment/disease/organism/publication field, incl. the ~16 study-quality flags |

## The local backend (no dump file needed)

Disbiome publishes no dump file, but its API returns each table whole in one GET and the
transfer and database sizes vary with provider updates. The `local` backend builds SQLite — fetch
`/experiment` + `/disease` + `/organism` + `/publication`, join in-memory, index by NCBI
taxid — via the shared `braidworks.core.localdb` plumbing. The cache fingerprint is a
content hash of the fetched tables (Disbiome has no release tag).

## Develop
Run the commands from this package directory.

```bash
make verify     # spec ↔ manifest, reachability, fingerprints (--strict adds golden vs the fixture)
make test       # conformance + contract + behavior, offline (live E2E self-skips)
make test-live  # opt-in: build the real DB from the API and resolve a known taxid
```

Extend it using [CONTRIBUTING.md](https://github.com/rafaelmdc/braidworks/blob/main/weavers/disbiome_weaver/CONTRIBUTING.md).
Reverse disease→taxon lookup already exists as `disbiome.list_taxa`. Build loop & boundaries: [AGENTS.md](https://github.com/rafaelmdc/braidworks/blob/main/AGENTS.md).

## Group-aware local reads

The current schema keeps indexed summary and compact evidence columns alongside the complete
joined JSON. Summary requests aggregate counts/names without reading full JSON;
compact requests read only their columns. Full records remain unchanged. Repeated
taxids share SQL/parsing within a single batch, with detached results.

Schema-1, schema-2 and schema-3 databases must be rebuilt using
`build_disbiome_weaver_configured(db_path=..., refresh=True, auto_setup=True)`.
Inputs match the source taxid exactly, at any recorded rank. Use `ncbi.taxon.id`
for genus or other identities; `ncbi.taxon.species_id` remains an alternative.
When both are present, the generic ID takes precedence, even if it has no match.
There is no ancestor fallback or propagation of genus observations to species.
Full records preserve the source organism identity; the provider does not supply
an explicit rank in the fixture, so this weaver does not infer one. The requested
`coverage` group (`microbe.disease.coverage`) reports the matched taxid, source
organism identities, reported rank or null, and filtered experiment count. This
slice reads the retained source records; ordinary summary/compact requests stay
light. A species-shaped input never relabels a genus observation as a species
measurement. Ancestor roll-up is intentionally unsupported.

## Construction and resource lifetime
For validated builders and client ownership, see
[shared configuration](../../docs/weaver-configuration.md).


## Snapshot validation

Builds validate that all four responses are arrays of objects with unique positive
primary IDs. Present foreign IDs must resolve; absent optional IDs are retained
as missing evidence and counted. Invalid experiment taxids are rejected. Validation
runs before opening the destination, and normal acquisition uses the shared atomic
publication boundary.

SQLite metadata includes `source_coverage` with each response's row count and
SHA-256, missing-join counts, and `build_completed_utc`. These identify the observed
responses; independent table requests do **not** constitute a frozen upstream
snapshot. Full joined records preserve provider fields. Current queries require
schema 4; rebuild older databases to obtain the current indexes and provenance.

Compact associations retain integer experiment, publication, organism and disease
IDs (null when absent), linking each observation to its full joined record.
The current database schema is 4; rebuild schema-1/2/3 databases.

Optional per-query `sample`, `method` and `outcome` parameters match provider
strings exactly, before summary counts or output projections. Omitted filters
retain all observations; missing context does not match an explicit filter.
Sample names are provider sample categories, not inferred anatomical sites.
Counts remain experiment counts and cannot establish causal disease effects.


### Exact disease and reverse taxon workflows

The requested `identity` group on `disbiome.list_diseases` emits full distinct
`disease.disbiome.id` and `disease.meddra.id` sets plus code/level/name evidence.
A provider disease ID is not a MedDRA code, and sharing a name does not merge IDs.
`disbiome.describe_disease` describes one provider ID's retained disease records.
`disbiome.list_taxa` takes either provider ID or MedDRA code (provider ID wins if
both are present). A code lookup preserves all distinct provider disease records
linked to that exact code. It emits the full sorted generic `ncbi.taxon.id` set,
not species IDs, with up to ten experiment/source organism/publication evidence
records and the true counts. Publication evidence preserves provider quality
reporting without deriving a study-quality score. Missing taxids stay out of the
fan set but remain evidence rows. Sample/method/outcome filters apply before counts.

Schema 4 adds reverse disease/code indexes; older databases require rebuilding.
Reverse traversal is exact observed evidence, with no ancestor propagation and
no causal or species-level claim inferred from a genus association.
