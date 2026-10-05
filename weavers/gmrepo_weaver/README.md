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
