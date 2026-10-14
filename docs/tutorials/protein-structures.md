# Find experimental structures for a protein list

You have a list of proteins and want to find related experimental structures before
choosing entries for further inspection. In this lesson, you will identify two proteins
through UniProt, retrieve their PDBe structure listings, inspect two related structures,
and save a table with coverage information.

You will learn how one source's identifier feeds another source, how to follow related
entities, and how to distinguish a useful result from a complete result. This lookup
does not assess whether a structure covers your region of interest or is suitable for
an experiment; that requires inspecting its sequence coverage and experimental context.

## Prepare your environment

You need Python 3.12+, [uv](https://docs.astral.sh/uv/getting-started/installation/),
and network access to UniProt and PDBe. Both APIs work without credentials.
If you already have a checkout, start from its root instead of cloning again.

```bash
git clone https://github.com/rafaelmdc/braidworks
cd braidworks
uv sync --package uniprot-weaver --package pdbe-weaver
```

This creates a local `.venv` and installs these sources with core. It does not download
biological databases. The selection can remove other workspace packages from this
venv; include all packages you want to retain if you already use the checkout.
Keep `uv run --no-sync` in the commands below to preserve the selected installation.
See [installation](../installation.md) for other environments.

## Connect one protein to its structure listing

Begin with UniProt accession `P04637`, the human p53 entry:

```bash
uv run --no-sync braidworks weave --have protein.query=P04637 \
    --want protein.name,structure.pdb.ids,structure.pdb.count --only uniprot,pdbe
```

`--have` describes the input you possess; `--want` names the information to retrieve.
UniProt resolves the query into a protein accession and name. PDBe consumes that
accession and returns its structure listing. The `--only` option keeps this lesson's
route within those two sources, even if your environment contains other weavers.

Look for a protein name, a list of PDB IDs and a total count. The APIs change, so
this lesson does not promise specific structure IDs or counts. You may see a count
larger than the displayed list: PDBe's display list is capped, while the count reports
the distinct structure total. A warning about selecting one `pdb.id` describes the
representative used for downstream lookup; it does not reduce that reported total.

If the command fails, inspect the diagnostic before interpreting the biology. Check
that both sources are installed and reachable. A no-match or technical error does not
establish that a protein lacks a structure. The [result guide](../results.md) explains
coverage and review outcomes.

## Inspect two related structures

Now ask for each structure's title and experimental method:

```bash
uv run --no-sync braidworks weave --have protein.query=P04637 \
    --want structure.pdb.title,structure.pdb.method --only uniprot,pdbe \
    --expand top:2 --format tsv
```

PDBe first lists related `pdb.id` values, then describes two members of that ordered
set. You should see up to two terminal rows with structure titles and methods, and
`parent`/`source_row` fields connecting them to the original protein input. The
source's order determines the selection; it is not a statement that these are the
best structures for your research question.

This is a bounded inspection, not the complete inventory. Later you can use
`--expand all`, subject to the run's expansion budget, and check truncation metadata
when completeness matters. Titles and methods describe PDB entries; a protein mapping
alone does not establish full-length sequence coverage or biological assembly relevance.
See [related-entity usage](../usage.md#follow-related-entities) for expansion controls.

## Prepare a two-protein batch

Create a file named `proteins.csv` in the checkout with this content:

```csv
protein.query
P04637
P38398
```

These accessions identify human p53 and BRCA1. Using accessions avoids the species and
representative-selection questions of gene-symbol search. For your own symbols, specify
an organism and check UniProt's selection rules; see [UniProt guidance](../../weavers/uniprot_weaver/README.md).

Run the batch, saving both a spreadsheet table and an inspectable run archive:

```bash
uv run --no-sync braidworks weave --in-file proteins.csv \
    --want protein.name,structure.pdb.ids,structure.pdb.count --only uniprot,pdbe \
    --format csv --archive protein-run.json > protein-structures.csv
```

Use a new archive filename for each run; Braidworks refuses to overwrite an existing
archive. The shell's `>` does overwrite an existing CSV, so choose a new table filename
when keeping previous outputs. Progress goes to stderr; the table goes to the file.

Open `protein-structures.csv` in a spreadsheet. This query does not expand related
structures, so each accepted protein row has a terminal outcome row. `source_row`
identifies its position in the input table. Keep the original CSV alongside the exports.

Check these columns before using the data:

| Column | Check |
|---|---|
| `status` | Whether the row resolved, needs review, failed or found no match. |
| `missing` | Whether any requested field is absent. A resolved row may still be partial. |
| `requires_review` | Whether you need to inspect an uncertain observation before using it. |
| `warnings`, `errors`, `diagnostics` | Selection limits, incomplete observations or technical failures. |
| `structure.pdb.ids`, `structure.pdb.count` | Displayed structure IDs versus the true distinct count reported by the lookup. |

The PDB ID column uses semicolon-separated values. Structured metadata cells such
as `missing` and diagnostics contain JSON; the `strands` cell retains typed values
and provenance. Retain unsuccessful rows in a coverage
report rather than dropping them as empty data. For this small example you should
normally obtain two resolved rows with names and structure information, but current
source availability governs the actual outcomes.

The archive preserves inputs, settings, observations and citations. It does not copy
provider databases or freeze the live APIs; it is separate from a resumable checkpoint.
For its exact contents and limitations, see [archive reference](../results.md#save-a-run-archive).

## Use the result for the next research step

You now have a protein-level structure listing and a way to inspect individual entries.
Before selecting a structure, check the entry's chain mapping, covered residues, method
and experimental context against your question. Braidworks provides observations and
provenance; you supply that scientific judgement.

For a larger protein list, replace the input rows while retaining the coverage columns.
For a complete per-structure table, follow the expansion guide and inspect budgets and
warnings. The [PDBe README](../../weavers/pdbe_weaver/README.md) describes additional
mapping and detail capabilities; [Python usage](../usage.md#query-from-python) shows
how to work with results in a script or notebook.
