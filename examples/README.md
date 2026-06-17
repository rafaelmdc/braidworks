# Examples

Ready-to-run input files so you can try Braidworks without making your own.

| File | Format | Use with |
|---|---|---|
| [`genes.txt`](genes.txt) | one gene symbol per line (`#` comments + blank lines ignored) | `--in-file genes.txt --in-type protein.query` |

## Quick start

From the repo root (after `uv sync --all-extras`):

```bash
# What each gene does + who it interacts with -> a TSV for your spreadsheet.
# `uv run` runs the command inside the project env; or `source .venv/bin/activate`
# once and drop the prefix.
uv run braidworks weave --in-file examples/genes.txt --in-type protein.query \
    --param organism=9606 --want go.biological_process,protein.interaction.partners \
    --format tsv > out.tsv
```

`--param organism=9606` pins each bare gene symbol to human (NCBI taxid 9606);
drop it (or change the taxid) for another species. See the main
[README](../README.md#for-biologists-the-bare-minimum) for the full walkthrough.
