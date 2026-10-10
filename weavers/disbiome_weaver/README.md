# disbiome_weaver

Microbe ↔ disease associations from **[Disbiome](https://disbiome.ugent.be)** (Ghent
University): given an organism by NCBI taxid, the diseases where its abundance is reported
**Elevated/Reduced** vs healthy controls (human host, MedDRA-coded). A terminal weaver off
the organism layer; chains straight behind `ncbi_weaver`.

- **Source:** https://disbiome.ugent.be (keyless JSON API on port 8080) · **License:** Open · **Cite:** https://doi.org/10.1186/s12866-018-1197-5 — Janssens et al., 2018
- **Backend:** `local` (a small SQLite built from the API; see below) · **Discoverable as** `disbiome`

## Capabilities

| Capability | Consumes | Produces (by group) |
|---|---|---|
| `disbiome.list_diseases` | `ncbi.taxon.id` or `ncbi.taxon.species_id` | **summary:** `microbe.disease.names`, `microbe.disease.count` · **associations:** `microbe.disease.associations` · **full:** `microbe.disease.records` |

Output slices, light → heavy (the mapper emits only the requested group):

| Group | What you get |
|---|---|
| `summary` | distinct disease names + how many records |
| `associations` | one compact row per experiment: disease, direction, method, sample, host |
| `full` | the complete joined blob — every experiment/disease/organism/publication field, incl. the ~16 study-quality flags |

## The local backend (no dump file needed)

Disbiome publishes no dump file, but its API returns each table whole in one GET and the
whole dataset is ~7 MB. The `local` backend builds a small SQLite **once** — fetch
`/experiment` + `/disease` + `/organism` + `/publication`, join in-memory, index by NCBI
taxid — via the shared `braidworks.core.localdb` plumbing. The cache fingerprint is a
content hash of the fetched tables (Disbiome has no release tag).

## Use it

Build the DB once, then it chains straight off `ncbi_weaver`
(`organism.name → ncbi.taxon.id → microbe.disease.*`):

```python
from disbiome_weaver import build_disbiome_weaver_configured

# Builds the ~7 MB DB on first use with explicit auto_setup consent (or
# BRAIDWORKS_AUTO_DOWNLOAD=1); no terminal prompt is implemented.
# Override the database location with db_path=.
weaver = build_disbiome_weaver_configured(auto_setup=True)
# In an app that wires a WeaverFactory, `disbiome_weaver.register(factory)` adds it as a provider.
```

For CLI discovery, first build the **default** cache with
`ensure_disbiome_db(auto=True)` from `disbiome_weaver.setup`. The default discovery
builder only inspects that cache; it does not build it. Then run:

```bash
braidworks run disbiome disbiome.list_diseases --have ncbi.taxon.id=816
```

## Develop

```bash
make verify     # spec ↔ manifest, reachability, fingerprints (--strict adds golden vs the fixture)
make test       # conformance + contract + behavior, offline (live E2E self-skips)
make test-live  # opt-in: build the real DB from the API and resolve a known taxid
```

Extend it ([CONTRIBUTING.md](https://github.com/rafaelmdc/braidworks/blob/main/weavers/disbiome_weaver/CONTRIBUTING.md)): reverse disease→microbe lookup, emitting
the taxid back out, etc. Build loop & boundaries: [AGENTS.md](https://github.com/rafaelmdc/braidworks/blob/main/AGENTS.md).

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/weavers/disbiome_weaver/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.

## Group-aware local reads (0.3.3)

Schema 2 keeps indexed summary and compact evidence columns alongside the complete
joined JSON. Summary requests aggregate counts/names without reading full JSON;
compact requests read only their columns. Full records remain unchanged. Repeated
taxids share SQL/parsing within a single batch, with detached results.

Schema-1 databases must be rebuilt using
`build_disbiome_weaver_configured(db_path=..., refresh=True, auto_setup=True)`.
Inputs match the source taxid exactly, at any recorded rank. Use `ncbi.taxon.id`
for genus or other identities; `ncbi.taxon.species_id` remains an alternative.
When both are present, the generic ID takes precedence, even if it has no match.
There is no ancestor fallback or propagation of genus observations to species.
Full records preserve the source organism identity; the provider does not supply
an explicit rank in the fixture, so this weaver does not infer one.

## Construction and resource lifetime

Supported builder options are explicit; unknown options raise
`BackendConfigurationError`. Empty construction remains safe for discovery.
See [configuration and lifetime](../../docs/weaver-configuration.md) for provider
configuration, source selection and owned/borrowed HTTP clients. Use
`async with weaver:` or `await weaver.aclose()` after requests finish.

## Snapshot validation (0.3.6)

Builds validate that all four responses are arrays of objects with unique positive
primary IDs. Present foreign IDs must resolve; absent optional IDs are retained
as missing evidence and counted. Invalid experiment taxids are rejected. Validation
runs before opening the destination, and normal acquisition uses the shared atomic
publication boundary.

SQLite metadata includes `source_coverage` with each response's row count and
SHA-256, missing-join counts, and `build_completed_utc`. These identify the observed
responses; independent table requests do **not** constitute a frozen upstream
snapshot. Full joined records preserve provider fields. Existing valid schema-2
caches remain readable; refresh to obtain the new build provenance.
