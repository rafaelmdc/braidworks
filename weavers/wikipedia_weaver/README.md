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


## Source response and failure handling

Pageviews responses must contain an items list with non-negative integer view counts. A returned monthly row with zero views is valid data; an empty items list is a miss. A missing/malformed items envelope is an error rather than a fabricated zero. Records retain the original query, including extra fields and whitespace.

Expected HTTP, JSON-decoding and explicitly validated source-data failures are returned as failure values. Cancellation and unrelated programming exceptions propagate. Existing successful output keys are preserved; consumers should handle `ERROR` separately from biological absence. Unknown extra source fields are allowed.

## Measurement scope

`wikipedia.pageviews.measurement` describes project, access, agent, monthly
granularity, start/end month and observed/requested bins. Scalar-only results
also carry a scope warning. The API default is exactly 12 completed months of
`all-agents` views; the local backend default is the stored dump month of `user`
views. Those defaults measure different scopes and should not be compared directly.

Declare the same `months`, `end_month` (YYYYMM) and `agent` parameters to request
a comparable metric. The API supports completed monthly windows; local supports
only `months=1`, its stored month and `agent=user`. An unsupported explicit scope
returns `ERROR` rather than silently substituting another metric. For example:

```bash
braidworks run wikipedia describe_pageviews --have wikipedia.title=Brown_bear \
  --param months=1 --param end_month=202505 --param agent=user
```

Duplicate or unexpected API bins, mismatched articles and measurement fields are
errors. Missing bins return an observed subtotal with incomplete coverage. The
local parser's completeness remains unknown, rather than claiming a complete dump.
The API interval ends at the last completed month, excluding the current partial month.

## Local dump identity and month selection

A requested month must match the database's recorded month. Reuse never silently
returns a January database for a February request: select another path or explicitly
use `refresh=True`. A prebuilt `db_path` can infer its stored month, while a supplied
`year` and `month` select the local backend. Supply both together; an identifiable
dump filename must agree with an explicitly requested month.

Schema 2 records the original compressed dump's SHA-256, source location, month and
measurement descriptor (`en.wikipedia`, all-access, user, monthly), plus parser
counts for valid, invalid and irrelevant rows. Caller-supplied text lines have a
separately labelled hash with record boundaries; they do not claim a compressed-file
hash. Negative/malformed relevant rows are rejected from aggregation and counted;
valid zero counts remain known zero. Invalid UTF-8 or decompression failures abort
the staged build. Source hashes and descriptors participate in the existing local
`SourceBinding` generation identity.

Local measurement output now reports the observed parser completeness. If parsing
was incomplete, an absent article returns an availability error rather than claiming
source absence; retained totals carry incomplete coverage. This completeness applies
to parsing the supplied artifact, not a guarantee about upstream traffic collection.
Schema 1 databases require rebuilding; no dump download occurs merely to inspect
an existing valid database.
