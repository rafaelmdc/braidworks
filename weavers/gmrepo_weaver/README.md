# gmrepo_weaver

GMrepo gut-metagenome abundances (taxid -> prevalence + median relative abundance, global and per-phenotype) weaver for Braidworks.

- **Source:** https://gmrepo.humangut.info
- **License:** Open (academic)
- **Cite:** https://doi.org/10.1093/nar/gkz764

## Setup and use

The implemented local backend reads a SQLite database built from the GMrepo API.
Installation and entry-point discovery do not build that database. Prepare the
default cache explicitly:

    from gmrepo_weaver.setup import ensure_gmrepo_db
    ensure_gmrepo_db(auto=True)

Then query it from the same installed environment:

    braidworks run gmrepo gmrepo.list_abundances --have ncbi.taxon.id=816

For a custom location, use the configured Python builder:

    from gmrepo_weaver.factory import build_gmrepo_weaver_configured
    weaver = build_gmrepo_weaver_configured(db_path="/path/to/gmrepo.sqlite")

The default abundance build does not include per-run sample profiles. To use
sample_profiles, build with profile_phenotypes (MeSH IDs) and profile_max_runs;
adding profiles to an existing database requires refresh=True. Those options are
setup configuration, not per-query CLI parameters.

    weaver = build_gmrepo_weaver_configured(
        auto_setup=True, refresh=True,
        profile_phenotypes=["D003093"], profile_max_runs=200,
    )

Outputs report associations and abundance summaries in the underlying studies;
they do not establish a causal effect. Deterministic fixture builders and golden
examples exercise the implementation without downloading the real database.

```bash
make verify   # check the weaver still matches its spec
make test     # run conformance + contract + golden tests
```

## Registering this weaver

The CLI discovers this installed weaver through its entry point. Python applications
can register a built instance directly in `BraidRegistry`. `WeaverFactory` registration
is optional construction support; it makes the builder available by ID, not a route.
For applications using that factory:

```python
from braidworks.core import WeaverFactory
import gmrepo_weaver

factory = WeaverFactory()
gmrepo_weaver.register(factory)        # makes "gmrepo" buildable
```

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/weavers/gmrepo_weaver/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.

## Acquisition coverage and sample denominators

Database schema 3 stores a JSON acquisition manifest in `meta.acquisition`. Each
taxon records a successful, empty or failed association request, including error
details. A failed taxon lookup returns `ERROR`; it cannot masquerade as zero
associations. `microbe.abundance.coverage` and the full record expose this scope.

Each requested phenotype records its run cap, selected runs, listing exhaustion,
fetched runs, successful empty runs, failed runs and individual run outcomes.
Sample results include this `coverage` and a `denominator` with successful fetched
runs (including empty profiles) and the catalog cohort size when known. `n_runs`
remains the count of runs with retained rows and is also named `n_runs_with_rows`;
it is not the cohort denominator. Capped or partially failed acquisition is explicitly
incomplete. Successfully acquired empty profiles return an empty result with
coverage; an unrequested phenotype returns an availability error.

Caller-supplied tables without an acquisition manifest expose unknown coverage
for retained rows, rather than asserting a complete cohort. Existing schema 1
databases must be rebuilt. Programming exceptions in acquisition workers propagate.

## Polite acquisition policy

Summary acquisition and optional profile acquisition are separate stages with
separate coverage sections. They share one request policy for the complete build:

```python
from gmrepo_weaver.acquisition import AcquisitionPolicy
from gmrepo_weaver.setup import ensure_gmrepo_db

ensure_gmrepo_db(
    auto=True,
    profile_phenotypes=["D003924"],
    profile_max_runs=20,
    acquisition_policy=AcquisitionPolicy(
        workers=4, requests_per_second=2.0,
        max_attempts=3, max_calls=10000,
        retry_backoff=1.0, max_retry_delay=60.0,
    ),
)
```

The configured builder accepts the same `acquisition_policy`. These defaults are
project policy, not a published GMrepo quota. At most `workers` jobs are queued;
all catalog, summary, listing, profile and retry calls share the rate gate and
`max_calls` budget. Only transport/time-out failures and HTTP 429/500/502/503/504
are retried, with exponential backoff. `Retry-After` is respected; a provider delay
beyond `max_retry_delay` returns a failed acquisition rather than retrying early.
Individual HTTP attempts still have the existing 180-second timeout.

Duplicate taxon IDs, requested phenotypes and profiles shared between phenotypes
reuse source work during this build. `meta.acquisition.requests` records policy,
actual attempt count, retry count and budget exhaustion. Failed per-resource work
retains incomplete coverage. Failure to acquire a required catalog aborts the
staged build and preserves an existing database.

The stages remain stored together in one atomically replaced SQLite database.
Adding profiles still requires a complete `refresh=True` rebuild; incremental
extension, persistent acquisition checkpoints and resume remain deferred. Existing
schema 1/2 databases require a refresh to obtain enforced logical identities and request-policy metadata.

### Logical row identities

Schema 3 keys overview rows by taxon/rank, associations by taxon/rank/phenotype,
and sample profiles by phenotype/run/taxon/rank. Repeated identical rows collapse
before storage and content hashing. Contradictory rows for the same key abort the
build, preserving an existing database during staged acquisition. Rebuild older
databases with `refresh=True`; rank completes all relevant lookup ordering.

## Construction and resource lifetime

Supported builder options are explicit; unknown options raise
`BackendConfigurationError`. Empty construction remains safe for discovery.
See [configuration and lifetime](../../docs/weaver-configuration.md) for provider
configuration, source selection and owned/borrowed HTTP clients. Use
`async with weaver:` or `await weaver.aclose()` after requests finish.

## Capabilities and output groups

| Capability | Input types | Output groups / expandable keys | Backends | Parameters |
|---|---|---|---|---|
| `gmrepo.list_abundances` | `ncbi.taxon.id` | `summary`, `associations`, `full` | `local` | — |
| `gmrepo.sample_profiles` | `disease.mesh.id` | `profiles`, `metadata` | `local` | — |
| `gmrepo.list_runs` | `disease.mesh.id` | `runs`; expands `metagenome.run_id` | `local` | `country`, `sex`, `project_id`, `QCStatus` |
| `gmrepo.describe_run` | `metagenome.run_id` | `run` | `local` | — |
| `gmrepo.list_phenotypes` | `ncbi.taxon.id` | `phenotypes`; expands `disease.mesh.id` | `local` | — |

These are the current declared capabilities. Output groups select fields computed
together; expandable keys identify related entities you can follow. See
[the spec](weaver.spec.toml) for exact output fields and parameter defaults, or
`braidworks weavers` for the installed inventory. Backend declarations do not imply
that optional local data are already configured.

## Complete offline Python example

```python
import asyncio
from braidworks.core import Strand, StrandSet
from gmrepo_weaver.factory import build_gmrepo_weaver_fixture

async def main():
    async with build_gmrepo_weaver_fixture() as weaver:
        result = (await weaver.execute_batch(
            'gmrepo.list_abundances',
            [StrandSet.from_strands("example", [Strand('ncbi.taxon.id', 816)])],
            requested_outputs=frozenset({'microbe.abundance.phenotype_names'}), backend="local",
        ))[0]
        print(result.to_json())
        result = (await weaver.execute_batch(
            'gmrepo.sample_profiles',
            [StrandSet.from_strands("example", [Strand('disease.mesh.id', 'D003093')])],
            requested_outputs=frozenset({'microbe.abundance.sample_profiles'}), backend="local",
        ))[0]
        print(result.to_json())

asyncio.run(main())
```

Summary queries project overview, names, count and acquisition scope; they do not
project association measurements. Full records and profiles require their groups.
Direct backend callers passing an empty group set retain the legacy full view.
The live build uses the taxon-centric summary endpoint with trailing slashes;
source_sample records current observed envelopes. Source setup still exposes
explicit acquisition budgets and optional profile scope.

### Source validation

Measurements use percentages in [0,100]; counts must be exact nonnegative SQLite integers. Invalid values report the field and original value. Missing measurements remain absent, and prevalence is undefined when there are no valid runs. Caller-supplied builds apply the same validation before creating a database.

Request `microbe.abundance.run_metadata` on `gmrepo.sample_profiles` for the
`metadata` group. Bounded acquisition retains the already-returned run listing
rows, including distinct run/sample/project IDs and provider metadata with its
original units and unknown values. No extra metadata request is issued per run.
The output reports selected/capped/empty/failed profile coverage; listing metadata
also survives profiles with no retained rows. Default profile output is unchanged.
Existing databases without retained metadata report `available=false`; rebuild
with the same bounded profile selection to acquire it. A capped subset is not a
complete cohort, and QC labels are not reinterpreted.


### Run and phenotype routing

`gmrepo.list_runs` takes `disease.mesh.id` and emits the full ordered
`metagenome.run_id` set plus `microbe.abundance.run_listing` (display capped at ten).
`gmrepo.describe_run` consumes one run ID and returns `microbe.abundance.run`:
retained metadata by phenotype, empty/failed acquisition outcomes, and profile rows.
Run, sample and project identities remain distinct; failed profiles are not empty
measurements. Old caller-supplied profiles remain drillable with unavailable metadata.
`gmrepo.list_phenotypes` maps a taxid to observed `disease.mesh.id` identifiers, which
can route into profile/run workflows. No name-based disease identity is inferred.

The configured builder accepts `profile_filters`, an exact source-field mapping
(`country`, `sex`, `project_id`, `QCStatus`), applied while paginating **before** the
`profile_max_runs` cap. Missing metadata never matches a filter. Request/call budgets
still bound scanning and incomplete acquisition is reported. Example:
`profile_filters={"country": "China", "QCStatus": 1}`.

The same declared parameters on `list_runs` refine only already-retained runs;
their coverage says this explicitly. They cannot recover excluded/unacquired data
or claim a complete cohort. Rebuild with builder filters for pre-cap selection.
The source's total valid-run denominator describes the unfiltered phenotype;
selected/fetched counts and filter provenance describe this acquisition.
