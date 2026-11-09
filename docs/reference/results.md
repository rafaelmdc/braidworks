# Result exports and run archives

Exact output contracts for the CLI and Python APIs. For choosing and saving an export,
see [the export guide](../how-to/check-results.md). For coverage and interpretation, see
[result meaning](../explanation/result-meaning.md).

## Command-line exports

`braidworks get` (and its `weave` alias), `resume` and `run` print the same rows as
Python's `Result` (see [Python results](#python-results)), one per terminal input or
fan-out leaf, including `error`, `review` and `unresolved` outcomes. Rows are in input
order; `row` is the one-based position of the accepted input row (comments and blank
lines are skipped), so duplicate inputs and fan-out children of one input stay
distinguishable. A traversal without `--want` shows the key it fanned over (e.g.
`pdb.id`) as its column.

| `--format` | Output |
|---|---|
| `human` (default) | Each row's input and `[status]`, one line per value with list sizes (`(2)`, `(25 of 312)`, `(25+)`), and `missing` types |
| `csv` / `tsv` | Exactly `Result.to_csv()`: `input`, `row`, `parent` (fan-out only), `status`, one column per requested field, a `<field>.total` after each sized list, `missing` |
| `json` | Exactly `Result.to_json()`: `summary`, `want`, `rows`, `references`, and `result`, the full engine result with strands, provenance, completion, candidates, diagnostics and truncations |
| `jsonl` | One row per line |

`run` (one capability, no routing) prints the same shape; its `result` holds the
capability's original results under `direct_results`. The summary line
(`5 inputs · 4 resolved · …`) and diagnostics go to stderr. Partial enrichment still
counts as `resolved`; inspect `missing` to require every requested field. A
`matched` column follows `status` when a resolved or error row's first step returns
identifying values its source always computes (UniProt: accession, gene, organism,
review status): what the input was matched to, as `field=value; …`, leaving out fields
you requested. A `why_missing` column follows `missing` when a resolved or error row lacks a field, giving
the reason per field, grouped: `structure.pdb.ids: pdbe has no match`, or
`microbe.disease.count: disbiome is not set up on this machine (run braidworks doctor)`.

## Python results

`bw.get` and `Session.get` return a `Result`; its rows, methods and the `Listing`
list type are in the [Python API reference](python-api.md). A row has `input`, `row`,
`parent` (expanded children only), `status`, one key per requested field (`None` when
absent), `missing`, `matched` (`{field: value}`, what the input matched) on resolved or
error rows whose source declares identifying fields, and `why_missing` (`{field: reason}`) on resolved or error rows that
lack a field. List fields hold a `Listing` with `.total` and `.complete`;
flat exports add a `<field>.total` column.

The older `fetch` returns a `FetchResult`: `get(id)` gives that input's values and
`column(type_id)` gives a mapping of IDs to values for that field. `unresolved`
includes inputs with no requested value, including paused reviews or errors;
inspect `review_queue` and `errors` to distinguish them. `review_required` retains
IDs that need curation. Inputs with partial results are in `resolved`.

The lower-level `ExecutionResult` holds enriched `StrandSet` objects in `resolved`,
no-match outcomes in `unresolved`, pending items in `review_queue`, and diagnostics
in `errors`. A resolved entity can also have branch errors. `total()` counts distinct
terminal entities; `fatal_errors()` identifies blocking failures. With fan-out,
terminal children are counted rather than original inputs. Result-scoped
`entity_refs` preserve relationships through JSON even when labels repeat.

## Run archives

An existing archive is never overwritten. The file is written
atomically with owner-only permissions. It retains initial input rows, CLI settings,
effective parameter defaults and overrides, planned routes, terminal outcomes and
executed completion/provenance, source manifests, declared backend fingerprints,
runtime versions, UTC start/end times and citations. Traversal archives store traversal
instructions as their plan; actual steps remain in the execution's completion records.
Unresolved/review/error outcomes are retained when an execution finishes, including
when strict mode returns a nonzero status. A planning failure, interruption or run-level
exception before a terminal result does not produce an archive. Failure to write the
archive returns a nonzero status.

The schema identifier is `braidworks.run-archive.v1`. Read it with any JSON reader;
`records` holds the detailed per-entity records behind the printed rows (values,
strands with confidence and provenance, completion, warnings, diagnostics and review
candidates), and routed `execution` can be loaded through
`ExecutionResult.from_json`. Direct runs retain each original `WeaveResult` under
`execution.direct_results`. Source manifests include discovered sources; only execution
completion and result references identify those actually used.

Archives retain observations, not copies of provider databases. An API fingerprint may
identify its interface rather than a frozen data release. Saved timestamps are the run
interval, not a timestamp for every HTTP request. Rerunning the same inputs against a
mutable source can produce different results.


## Spreadsheet value cells

Value columns render lists as semicolon-separated values and dictionaries as compact
JSON; `<field>.total` gives a list's true size. Use `--format json` (its `result`
field) or a run archive to keep nested typed values, confidence and provenance.
The [Python result](../../braidworks-core/src/braidworks/_result.py) defines these rules.
