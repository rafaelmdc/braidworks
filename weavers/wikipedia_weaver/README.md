# wikipedia_weaver

Wikipedia pageviews (enwiki article title -> recent pageview count) weaver for Braidworks.

- **Source:** https://wikimedia.org/api/rest_v1/
- **License:** CC0-1.0
- **Cite:** Wikimedia REST API — pageviews. https://wikimedia.org/api/rest_v1/

## Use it

The implemented keyless API backend sums pageviews for an English Wikipedia title
over the trailing twelve whole months. A title may come from wikidata_weaver.

    braidworks run wikipedia describe_pageviews --have wikipedia.title=Brown_bear

This is a page-popularity measure, not a biological measurement. Its API fingerprint
is the window-end month; the underlying live service can still revise its data.

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

## Registering this weaver

A weaver is only reachable to the braider once its provider is registered in the
application's `WeaverFactory`. Wherever you assemble the factory:

```python
from braidworks.core import WeaverFactory
import wikipedia_weaver

factory = WeaverFactory()
wikipedia_weaver.register(factory)        # makes "wikipedia" buildable
```

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/weavers/wikipedia_weaver/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.
