# Check coverage and export results

Use this guide after a query to retain useful values alongside failed, missing or
uncertain observations. For the reason these distinctions matter, read
[result meaning](../explanation/result-meaning.md).

## Check coverage and review

Before using an export, check each original input's terminal rows:

1. Inspect each row's `status`; errors are explained on stderr. A technical failure is
   not a negative biological observation.
2. Inspect `missing` for requested fields. A resolved row can still be partial;
   `why_missing` says why each field is absent (the source failed or is not set up,
   found no match, or was not reached).
3. Inspect `review` rows and their candidates (`braidworks runs RUN_ID` for a saved
   run, or the `result` field of `--format json`). Resolve uncertain matches before
   treating them as accepted identity.
4. Inspect warnings and truncations, especially after expansion; truncations are
   reported on stderr. Use `row` and `parent` to regroup children with the original
   inputs, and `<field>.total` to see when a list is partial.

Retain unsuccessful rows in your coverage report. See [exact row fields](../reference/results.md#command-line-exports)
and [review continuation](cache-and-resume.md#resolve-a-saved-review).

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

Every format prints the same rows as Python's `Result`, labelled by your input,
including errors and review rows; CSV/TSV/JSON are byte-for-byte what `to_csv()` /
`to_json()` give in Python. List values use `; ` delimiters with a `<field>.total`
column. For confidence, provenance and candidates use `--format json` (its `result`
field) or `--archive`. See [export reference](../reference/results.md#command-line-exports).

## Read Python results

With `bw.get`, check `result.summary()`, each row's `status` and `missing`, and
`result.review` for paused matches; list fields carry their size (`.total`,
`.complete`). [Work in Python](work-in-python.md) has the recipes. Inputs with partial
values are still `resolved`; check `missing` before using them. For lower-level result buckets,
counts and serialization, see [Python result reference](../reference/results.md#python-results).

## Save a run archive

With PDBe installed, save a CSV and a separate observation archive:

```bash
uv run braidworks get P04637 --have protein.uniprot.accession --want structure.pdb.ids \
  --only pdbe --format csv --archive run.json > structures.csv
```

Choose a new archive filename: an existing archive is never overwritten. Shell
redirection does overwrite an existing CSV. Archives retain terminal executions,
including unsuccessful rows, but a planning failure or interruption before a terminal
result does not create one. Failure to write an archive returns a nonzero status.

An archive is an observation export, separate from the checkpoint store used by
`resume`. For archive contents, permissions, loading and reproducibility limits,
see [archive reference](../reference/results.md#run-archives). To continue interrupted
work, use [saved runs](cache-and-resume.md).

For exception types, fallback boundaries and diagnostic categories, see the
[failure contract](../reference/failures.md).
