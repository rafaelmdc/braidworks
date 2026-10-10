# Understand and export results

A query can return useful data even when another source has no match or fails.
Start by checking coverage: which requested fields did each input actually receive?
For runnable queries, see [usage](usage.md).

## Check coverage and review

| Outcome | What to do |
|---|---|
| Resolved | Use the returned values and check `missing` for requested fields that were not produced. |
| Unresolved | Keep the input in your coverage report; the source found no match along the attempted route. |
| Review | Inspect the candidates or review flag before using an uncertain match. |
| Error | Read the diagnostic. A technical failure does not establish biological absence. |

Resolved means **at least one** target was produced. It does not mean every requested
field is present. A no-match likewise does not prove that an organism lacks a trait
or that a protein has no biological role; it describes the source lookup.

Ambiguous resolver matches pause by default. Expansion controls how many related
entities to follow; it does not authorize choosing an ambiguous match. Some lookup
capabilities select a representative instead of emitting candidates. In particular,
UniProt gene-symbol search returns one representative: specify the organism and use
an accession when you need an exact protein.

CLI output goes to stdout; progress and diagnostics go to stderr. Ordinary queries
return nonzero for fatal failures. Add `--strict` to also fail for unresolved or
review-required outcomes. Partial enrichment may still succeed; validate `missing`
when your analysis requires all fields. Direct `run` returns nonzero for backend
errors. See `braidworks weave --help` and `braidworks run --help` for options.

## Choose an export

Use CSV/TSV for spreadsheets, JSONL for line-by-line processing, or JSON for structured
analysis. All machine formats retain terminal outcomes, including errors and review
rows. Do not discard those rows when calculating coverage.

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

## Read Python results

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

## Save a run archive

Add `--archive run.json` to `braidworks weave` or `braidworks run` to save a
self-contained JSON record alongside the usual stdout format. For example:

```bash
uv run --no-sync braidworks weave --have protein.uniprot.accession=P04637 --want structure.pdb.ids \
  --only pdbe --format csv --archive run.json > structures.csv
```

Use a new filename: an existing archive is never overwritten. The file is written
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

For restarting work, use a [saved run](persistence.md). An archive is an observation
export, separate from the checkpoint store used by `resume`.
