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

A weaver is only reachable to the braider once its provider is registered in the
application's `WeaverFactory`. Wherever you assemble the factory:

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

Database schema 2 stores a JSON acquisition manifest in `meta.acquisition`. Each
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
schema 2 databases remain readable; refresh to obtain the request-policy metadata.
