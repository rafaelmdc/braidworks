# Wikipedia source reference

Exact source outputs, coverage and implementation constraints. Start with
[the package overview](README.md) for setup and query entry points.

## Capabilities

<!-- weaverkit:capabilities:start -->
| Capability | Input types | Output groups / expandable keys | Backends | Parameters |
|---|---|---|---|---|
| `describe_pageviews` | `wikipedia.title` | `core`, `series` | `api`, `local` | `months`, `end_month`, `agent` |
<!-- weaverkit:capabilities:end -->

These are the current declared capabilities. Output groups select fields computed
together; expandable keys identify related entities you can follow. See
[the spec](weaver.spec.toml) for exact output fields and parameter defaults, or
`braidworks weavers` for the installed inventory. Backend declarations do not imply
that optional local data are already configured.

## Registering this weaver

The CLI discovers this installed weaver through its entry point. Python applications
can register a built instance directly in `BraidRegistry`. `WeaverFactory` registration
is optional construction support; it makes the builder available by ID, not a route.
For applications using that factory:

```python
from braidworks.core import WeaverFactory
import wikipedia_weaver

factory = WeaverFactory()
wikipedia_weaver.register(factory)        # makes "wikipedia" buildable
```

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
local backend reports parsing completeness for the supplied artifact, without
claiming complete upstream traffic collection.
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

Local measurement output reports the observed parser completeness. If parsing
was incomplete, an absent article returns an availability error rather than claiming
source absence; retained totals carry incomplete coverage. This completeness applies
to parsing the supplied artifact, not a guarantee about upstream traffic collection.
Schema 1 databases require rebuilding; no dump download occurs merely to inspect
an existing valid database.

## Construction and resource lifetime
For validated builders and client ownership, see
[shared configuration](../../docs/weaver-configuration.md).


Request `wikipedia.pageviews.series` for ordered observed `{month, views}` bins
and `wikipedia.pageviews.title` for title provenance (the `series` group).
Missing months are not zero-filled; the existing measurement output reports
completeness. The API supports the existing window/agent parameters; a local dump
provides its one acquired user-traffic month. Titles remain English Wikipedia
titles, with no automatic redirect resolution or traffic aggregation.
