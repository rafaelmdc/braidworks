# Check coverage and export results

Use this guide after a query to retain useful values alongside failed, missing or
uncertain observations. For the reason these distinctions matter, read
[result meaning](explanation/result-meaning.md).

## Check coverage and review

Before using an export, check each original input's terminal rows:

1. Inspect `status`, `errors` and diagnostics. A technical failure is not a negative
   biological observation.
2. Inspect `missing` for requested fields. A resolved row can still be partial.
3. Inspect `requires_review` and candidates. Resolve uncertain matches before treating
   them as accepted identity.
4. Inspect warnings and truncations, especially after expansion. Use `source_row` and
   parent relationships to regroup children with the original inputs.

Retain unsuccessful rows in your coverage report. See [exact record fields](reference/results.md#machine-records)
and [review continuation](persistence.md#resolve-a-saved-review).

CLI data go to stdout; progress and diagnostics go to stderr. Ordinary queries fail
for fatal errors. Add `--strict` to also fail for unresolved or review-required outcomes;
still check `missing` when every requested field is required. Direct `run` returns
nonzero for backend errors.

## Choose an export

| Consumer | Format |
|---|---|
| Spreadsheet | `--format csv` or `--format tsv` |
| Structured analysis | `--format json` |
| Line-by-line processing | `--format jsonl` |

All machine formats retain terminal outcomes, including errors and review rows.
Select spreadsheet columns by name. Requested list values use display delimiters;
structured metadata use JSON cells. Use JSON/JSONL or `strands` for nested typed values.
See [export reference](reference/results.md).

## Read Python results

For `fetch`, inspect `unresolved`, `review_queue`, `review_required` and `errors`
alongside `get(id)` or `column(type_id)`. Inputs with partial values can still appear
in `resolved`; check required keys before using them. For lower-level result buckets,
counts and serialization, see [Python result reference](reference/results.md#python-results).

## Save a run archive

With PDBe installed, save a CSV and a separate observation archive:

```bash
uv run --no-sync braidworks weave --have protein.uniprot.accession=P04637 --want structure.pdb.ids \
  --only pdbe --format csv --archive run.json > structures.csv
```

Choose a new archive filename: an existing archive is never overwritten. Shell
redirection does overwrite an existing CSV. Archives retain terminal executions,
including unsuccessful rows, but a planning failure or interruption before a terminal
result does not create one. Failure to write an archive returns a nonzero status.

An archive is an observation export, separate from the checkpoint store used by
`resume`. For archive contents, permissions, loading and reproducibility limits,
see [archive reference](reference/results.md#run-archives). To continue interrupted
work, use [saved runs](persistence.md).

For exception types, fallback boundaries and diagnostic categories, see the
[failure contract](reference/failures.md).
