# Result exports and run archives

Exact output contracts for the CLI and Python APIs. For choosing and saving an export,
see [the export guide](../results.md). For coverage and interpretation, see
[result meaning](../explanation/result-meaning.md).

## Machine records

Machine exports (`json`, `jsonl`, `csv`, `tsv`) include one record per terminal
entity or fan-out leaf, including fatal `error` outcomes. `source_row` is the
one-based ordinal of an accepted input row (comments and blank lines are skipped);
it survives fan-out even when input labels repeat. `outcome` is unique within the
output, and `entity`/`parent` retain their human-readable labels. Records are ordered
by source row, keeping sibling order. Neither identifier is a persistent database ID.

Every record carries `status`, `missing` requested types, `requires_review`, warnings,
errors, structured diagnostics, completion steps and review candidates. `strands`
contains the exported values with confidence, provenance and metadata. `references`
is the run's bibliography, including reroute sources; it is not per-row attribution.
CSV/TSV carry these structured fields as JSON cells, with requested value columns
alongside them. Their headers now include outcome metadata; consumers should select
columns by name. Partial enrichment still counts as resolved; inspect `missing` to
require every requested field. Human diagnostics continue on stderr.

## Python results

`fetch` returns a `FetchResult`: `get(id)` gives that input's values and
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
`records` matches the JSON stdout records, and routed `execution` can be loaded through
`ExecutionResult.from_json`. Direct runs retain each original `WeaveResult` under
`execution.direct_results`. Source manifests include discovered sources; only execution
completion and result references identify those actually used.

Archives retain observations, not copies of provider databases. An API fingerprint may
identify its interface rather than a frozen data release. Saved timestamps are the run
interval, not a timestamp for every HTTP request. Rerunning the same inputs against a
mutable source can produce different results.


## Spreadsheet value cells

Requested value columns render lists as semicolon-separated values and dictionaries
as JSON; structured outcome metadata use JSON cells. Use the `strands` JSON cell or
JSON/JSONL output to retain nested typed values without parsing display delimiters.
The [CLI renderer](../../braidworks-core/src/braidworks/core/cli.py) defines these rules.
