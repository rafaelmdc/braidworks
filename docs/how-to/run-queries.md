# Run a query from the command line

Look up fields for an identifier you have, across the installed sources, with
`braidworks get`. For scripts and notebooks see [work in Python](work-in-python.md); to
build a query visually, [use the browser](use-the-browser.md).

Complete the [installation guide](install.md) first. Commands below run from the
checkout with `uv run`; after activating `.venv/bin/activate`, you can use the bare
`braidworks` command. See [sources](choose-sources.md) for local-data setup.

## Look up fields for an ID

```bash
uv run braidworks get P04637 --have protein.query \
    --want protein.name,structure.pdb.ids
```

The ID comes first; `--have` names what it is and `--want` names the fields to
retrieve. Here UniProt resolves the query and PDBe lists related experimental
structures; both must be installed and network-accessible. Not sure of a field name?
[Find a field](find-a-field.md).

The output labels each row by your input, with its status, what the input matched and
the size of each list:

```text
P04637  [resolved]
  matched: protein.uniprot.accession=P04637; protein.gene=TP53; protein.organism=Homo sapiens; protein.reviewed=reviewed
  protein.name: Cellular tumor antigen p53
  structure.pdb.ids (321): 9r2q; 9u4d; 9r2m; …
```

For a gene symbol, set the species:

```bash
uv run braidworks get TP53 --have protein.query --param organism=9606 \
    --want protein.name,structure.pdb.ids
```

`9606` is the human NCBI taxid. Symbol search returns a representative entry; an
accession is more specific. Check the `matched` line: without `organism`, `BRCA1`
matches `Rattus norvegicus` (accession O54952), and only `matched` shows it. Check the source's selection rules when interpreting
name-based queries. To look up many IDs, [process a batch](process-a-batch.md); to get
details for every structure or ortholog, [follow related entities](follow-related-entities.md).

## If the query fails

```bash
uv run braidworks doctor
```

`doctor` lists each installed source and whether it is ready, partly ready, or needs a
local database first, and names sources in the checkout that are not installed. A
"no route" error names the input or output that nothing installed handles, suggests
close field names, and says which missing source would handle it.

## Call one source directly

Use `run` when you already know the capability you need:

```bash
uv run braidworks run pdbe describe_structure --have pdb.id=1tup \
    --want structure.pdb.title,structure.pdb.method
```

`get` plans across sources; `run` calls one named source capability and prints the
same rows.

## Configure a run

| Need | Option or guide |
|---|---|
| Restrict discovery to sources you need | `--only uniprot,pdbe` |
| Set a filter or source option | `--param NAME=VALUE`; `--param CAPABILITY:NAME=VALUE` scopes it to a step |
| Choose local/API backends | `--policy local_first\|api_first\|local_only\|api_only` |
| Handle ambiguous resolver matches | `--review-policy halt` by default; `allow_continue` keeps review flags |
| Require a minimum confidence score | `--confidence-threshold 0.8`; scores are source heuristics, not calibrated probabilities |
| Export a table | `--format csv\|tsv\|json\|jsonl`; see [process a batch](process-a-batch.md#choose-the-export) |
| Save observations and citations | `--archive run.json`; [archive reference](check-results.md#save-a-run-archive) |
| Cache lookups or restart saved work | [Cache and saved runs](cache-and-resume.md) |
| Pace source requests | [HTTP pacing](set-request-rates.md) |

`--strict` also fails on unresolved or review-required rows. Partial results still need
coverage checks: read [results](check-results.md) before using exports in an analysis.
Every option of every command is in the [CLI reference](../reference/cli/index.md).
