# Process a batch from the command line

Look up many inputs in one run and export a table. This guide assumes you can already
[run a single query](run-queries.md). Commands run from the checkout with `uv run`.

## Pass a few IDs as arguments

List the values after `get` and name their field once with `--have`:

```bash
uv run braidworks get P04637 P38398 Q9Y6K9 --have protein.query \
    --want protein.name,structure.pdb.ids --format tsv > structures.tsv
```

Each ID becomes one row, labelled by the ID. A repeated ID stays a separate row.

## Read one ID per line from a file

```bash
uv run braidworks get --in-file accessions.txt --in-type protein.query \
    --want protein.name,structure.pdb.ids --format tsv > structures.tsv
```

Create `accessions.txt` with your identifiers first. Blank lines and `#` comments are
skipped. For a supplied gene-symbol list, use [`examples/genes.txt`](../../examples/genes.txt)
with `--param organism=9606`.

## Read a table whose rows start from different fields

For CSV or TSV, use field names as headers. This file starts some rows from a query and
others from an exact accession:

```csv
protein.query,protein.uniprot.accession
P04637,
,P38398
```

Save it as `inputs.csv`, then run:

```bash
uv run braidworks get --in-file inputs.csv \
    --want structure.pdb.ids --format csv > structures.csv
```

Empty cells are absent inputs. Rows are grouped by the input fields they have and
planned before execution starts. Read stdin with `--in-file -` (for example from
another command in a pipeline).

## Add a value to every row

`--have TYPE=VALUE` applies one value to every ID or row; a row's own value wins:

```bash
uv run braidworks get --in-file genes.txt --in-type protein.query \
    --have ncbi.taxon.id=9606 --want protein.name --format csv
```

## Choose the export

| Consumer | Format |
|---|---|
| Spreadsheet or pandas | `--format csv` or `--format tsv` |
| Structured analysis (with provenance and candidates) | `--format json` |
| Line-by-line processing | `--format jsonl` |

Data go to stdout; progress, the summary line and diagnostics go to stderr. Every
format keeps unresolved, review and error rows. Before using the table, check each
row's `status` and `missing` columns as described in [reading results](check-results.md);
add `--strict` to make the run fail when any row is unresolved or needs review.
