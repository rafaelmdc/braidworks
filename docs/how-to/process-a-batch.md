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

Empty cells are absent inputs. Each result row is labelled by its input row's
values: `P04637` for a row with one value, `protein.query=P04637; protein.uniprot.accession=…`
for a row with several. Rows are grouped by the input fields they have and
planned before execution starts. Read stdin with `--in-file -` (for example from
another command in a pipeline).

## Apply the same setting or value to every row

A source option, such as the species for gene symbols, applies to every row. Set it
with `--param`:

```bash
uv run braidworks get --in-file examples/genes.txt --in-type protein.query \
    --param organism=9606 --want protein.name --format csv
```

`--have TYPE=VALUE` is different: it adds an input field with that value to every ID
or row (a row's own value wins). It matters only when a step starts from that field,
and it never sets a source option: `--have ncbi.taxon.id=9606` does **not** restrict
gene symbols to human, `--param organism=9606` does.

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
