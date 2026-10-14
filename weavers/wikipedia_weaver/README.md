# wikipedia_weaver

Retrieve English Wikipedia pageview totals and monthly observations as attention signals. The
API defaults to twelve completed months of all-agent traffic; a local dump describes one month
of user traffic. Declare matching scope before comparing them. Pageviews are not biological
measurements.

- **Source:** https://wikimedia.org/api/rest_v1/
- **License:** CC0-1.0
- **Cite:** Wikimedia REST API — pageviews. https://wikimedia.org/api/rest_v1/

## Capabilities

| Capability | Use it to |
|---|---|
| `describe_pageviews` | Retrieve pageview totals, scope and optional series |

See [source reference](REFERENCE.md#capabilities) for exact inputs, output groups, backends and parameters,
or inspect the [spec](weaver.spec.toml).

## Run a query

The implemented keyless API backend sums pageviews for an English Wikipedia title
over the trailing twelve whole months. A title may come from wikidata_weaver.

    braidworks run wikipedia describe_pageviews --have wikipedia.title=Brown_bear

This is a page-popularity measure, not a biological measurement. Its API identity includes the effective source and measurement window;
the live service can still revise data.

## Optional local backend

The local backend indexes one monthly pageview_complete dump. Its total covers
that one month, unlike the API's twelve-month window. Build from an existing dump
or explicitly authorize a download, and always supply the month:

    from wikipedia_weaver.factory import build_wikipedia_weaver
    weaver = build_wikipedia_weaver(
        db_path="/path/to/pageviews.sqlite",
        dump_path="/path/to/pageviews-202501-user.bz2",
        year=2025, month=1, auto_setup=True,
    )

A custom database path is Python configuration. CLI discovery uses the default
cache path and does not automatically acquire dumps. Offline API fixtures and
local-dump tests are implemented.

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
