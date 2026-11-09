# Your first query in the browser

In this lesson you look up two human genes, TP53 and BRCA1, in the browser and get
each one's protein name, its experimental PDB structures and its Reactome pathways.
Along the way you see how a row that matches nothing is reported, which route
answered your question, which sources to cite, and how to download the table. It takes
about ten minutes and needs no programming.

You need Python 3.12 or newer, [uv](https://docs.astral.sh/uv/getting-started/installation/)
and an internet connection. The sources used here (UniProt, PDBe and Reactome) are free
public APIs and need no account.

## Start the browser

In a terminal, get the code, install every source with the browser interface, and
start it. The install downloads no biological databases. If you already have a
checkout, start from its root instead of cloning again.

```bash
git clone https://github.com/rafaelmdc/braidworks
cd braidworks
uv sync --all-extras
uv run braidworks serve
```

The command prints an address such as `http://127.0.0.1:8765` and opens it in your
browser. Leave the terminal running; press Ctrl-C there when you finish the lesson.

## Paste your IDs

The page opens on **Look up what you need for a list of IDs**. In **1 Your IDs**
(the grey `P04637` / `BRCA1` is only a placeholder; the count reads **0 IDs**), paste
three lines:

```text
TP53
BRCA1
NOTAGENE
```

The third line is deliberately not a gene, so you can see how a miss looks. Under the
box, the page counts **3 IDs**.

## Say what they are

**2 What are they?** offers the input types the installed sources accept. Braidworks
does not guess what your IDs are, because the type decides which sources can start
from them. `protein.query` is already selected: "the text you start from — a gene
symbol, protein name, or accession". Leave it selected.

## Choose the fields

In **3 What do you want?**, type `protein name` into the search box. The best match is
`protein.name`, "this protein's recommended name", provided by UniProt. Tick it.

Search again for `pdb structures` and tick `structure.pdb.ids`, "experimental PDB
structures of this protein". Then search for `pathway names`. Two close matches appear:
`pathway.reactome.display_name` describes one pathway, while `pathway.reactome.names`
lists "the Reactome pathways this protein takes part in". Read the descriptions and
tick `pathway.reactome.names`.

The three fields now sit as chips above the search results. Some results are greyed
out with "no route from protein.query": the installed sources cannot reach those
fields from a gene symbol.

## Set the species

Once you have chosen fields, **Options for this route** shows what the route accepts.
UniProt's `organism` option explains that a bare gene symbol otherwise resolves to
whichever species ranks first. Type `9606`, the NCBI taxon ID for human, so that TP53
means the human gene.

## Run it

The button now reads **Get 3 fields for 3 IDs**. Click it. Progress appears beside the
button, then a summary:

```text
3 inputs · 2 resolved · 1 unresolved · 0 need review · 0 errors
```

The results table has one row per ID, labelled by what you pasted. Under each ID, in
grey, is what it was matched to: for TP53, `accession: P04637 · gene: TP53 · organism:
Homo sapiens · reviewed: reviewed`. That is how you know the symbol meant the human gene.

- **TP53** is `resolved`: Cellular tumor antigen p53, its PDB structures and its
  Reactome pathways. Each list shows its first members and its size, such as "321 in
  total"; click **+318 more** to see the rest.
- **BRCA1** is `resolved`: Breast cancer type 1 susceptibility protein, with its own
  structures and pathways.
- **NOTAGENE** is `unresolved`. Its cells show —, and **Missing** names all three
  fields.

The sources update continuously, so your counts can differ from the ones in this
lesson. Click **1 unresolved** in the status counts to show only that row; click it
again to show every row.

## See how it was answered

Beside the table, **How this was answered** lists the steps that ran:

1. **uniprot** `resolve_protein`, protein.query → protein.name and
   protein.uniprot.accession, via api, 2 found, 1 no match, options organism = 9606.
2. **reactome** `list_pathways`, protein.uniprot.accession → pathway.reactome.names,
   2 found, 1 skipped (no input).
3. **pdbe** `list_structures`, protein.uniprot.accession → structure.pdb.ids, 2 found,
   1 skipped (no input).

UniProt turned your symbols into accessions, and the other two sources started from
those. NOTAGENE was skipped by Reactome and PDBe because UniProt found no accession
for it: the miss happened at the first step, not in the later sources.

**Sources to cite** lists PDBe, Reactome and UniProt, with each one's licence and
citation. Use these when you publish the data.

## Download the table

Click **CSV**. The browser saves `braidworks-results.csv`. Its header is:

```text
input,row,status,matched,protein.name,structure.pdb.ids,structure.pdb.ids.total,pathway.reactome.names,pathway.reactome.names.total,missing
```

`matched` records what each ID was matched to (its UniProt accession, gene, species
and review status), so a reader of the file can check that TP53 really meant the human
gene. Lists are separated by `; `, and each `.total` column holds the list's true size. The
file is exactly what Python's `result.to_csv()` and `braidworks get --format csv` give
for the same query, so you can switch between the browser, a notebook and the command
line without the table changing.

## What you did

You pasted identifiers, named their type, found fields by meaning, set the one option
the route needed, and got a table that reports every input, including the one that
matched nothing. You saw which sources answered and how to cite them, and you saved
the table as a spreadsheet.

Next:

- Save this query with **Save as example** so you can rerun it from **Start from an
  example**.
- [Use the browser](../how-to/use-the-browser.md) for batches from a file, reviewing
  ambiguous matches, advanced settings and saved runs.
- [How routes are planned](../explanation/how-routes-are-planned.md) explains what
  **Explore sources** shows and why some fields are out of reach.
- The same lookup in Python: [your first analysis in Python](first-analysis-in-python.md).
