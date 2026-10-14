# gmrepo_weaver

Retrieve gut-metagenome abundance summaries, phenotype associations, runs and sample profiles
from an acquired GMrepo database. Coverage and sample denominators depend on the retained data
and acquisition settings. Per-run profiles require explicit inclusion at build time. These
observations do not establish causal effects.

- **Source:** https://gmrepo.humangut.info
- **License:** Open (academic)
- **Cite:** https://doi.org/10.1093/nar/gkz764

## Capabilities

| Capability | Use it to |
|---|---|
| `gmrepo.list_abundances` | Retrieve taxon abundance and phenotype summaries |
| `gmrepo.sample_profiles` | Retrieve acquired sample profiles for a phenotype |
| `gmrepo.list_runs` | List acquired runs for a phenotype |
| `gmrepo.describe_run` | Inspect a retained run |
| `gmrepo.list_phenotypes` | List phenotype identities for a taxon |

See [source reference](REFERENCE.md#capabilities-and-output-groups) for exact inputs, output groups, backends and parameters,
or inspect the [spec](weaver.spec.toml).

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

## Setup, interpretation and contribution

Use [checkout or wheel installation](../../docs/installation.md) with core and the
sources needed for your route. From the checkout, prefix commands above with
`uv run --no-sync`; a bare command assumes the environment is activated.
Source installation does not acquire optional biological databases.

[Source reference](REFERENCE.md) retains coverage, selection, failure and resource
rules. [Builder configuration](../../docs/weaver-configuration.md) documents supported
options and ownership; close configured weavers after work completes. See
[contributing](CONTRIBUTING.md) to extend this source, and run package checks from
this package directory. Current installation does not assume package-index publication.

## Software license

The software uses [MIT](LICENSE). Provider data retain their source licenses and
attribution requirements above; the manifest data license does not license this code.
