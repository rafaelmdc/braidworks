# Your first analysis in Python

In this lesson you take two human genes, TP53 and BRCA1, and collect for each one its
protein name, its Gene Ontology terms and its experimental PDB structures. Then you
put the results in a pandas table and list the sources to cite. It takes about ten
minutes in a Jupyter notebook or any Python prompt.

You need Python 3.12 or newer, [uv](https://docs.astral.sh/uv/getting-started/installation/)
and an internet connection. The sources used here (UniProt, QuickGO and PDBe) are free
public APIs and need no account.

## Before you start

In a terminal, get the code and create its environment, which includes every source
and pandas support. It downloads no biological databases. If you already have a
checkout, start from its root instead of cloning again.

```bash
git clone https://github.com/rafaelmdc/braidworks
cd braidworks
uv sync --all-extras
uv run --with jupyter jupyter notebook
```

Open a new notebook. Every code block below is one cell. (Without Jupyter,
`uv run python` gives you a prompt that works the same way, except that a table is
printed only when you pass it to `print()`, and pandas may hide middle columns behind
`...` in a narrow terminal.)

## Find the fields you want

Braidworks names every piece of data with a field such as `protein.name`. You don't
need to know them in advance; search by meaning:

```python
import braidworks as bw

bw.find("gene ontology terms", limit=1)
```

```text
go.term  A Gene Ontology term id.
         (quickgo; from protein.uniprot.accession)
```

The answer tells you the field (`go.term`), which source provides it (QuickGO) and
what it starts from (a UniProt accession). Search for structures the same way:

```python
bw.find("pdb structures", limit=1)
```

```text
structure.pdb.ids  Experimental PDB structures of this protein.
                   (pdbe; from protein.uniprot.accession)
```

You will start from gene symbols, not accessions. That is fine: Braidworks finds the
route from what you have to what you want, through UniProt.

## Look up your genes

Ask for all three fields at once. `have` says what your values are; `organism` pins
the symbols to human, because the same symbol exists in many species. A third,
made-up symbol shows what a miss looks like:

```python
result = bw.get(
    ["TP53", "BRCA1", "NOTAREALGENE"],
    have="protein.query",
    want=["protein.name", "go.term", "structure.pdb.ids"],
    organism="9606",
)
result
```

```text
<braidworks.Result 3 inputs · 2 resolved · 1 unresolved · 0 need review · 0 errors>
  TP53 [resolved] protein.name='Cellular tumor antigen p53', go.term='GO:0000122; …', structure.pdb.ids='9r2q; 9u4d; …'
  BRCA1 [resolved] protein.name='Breast cancer type 1 susceptibility prot…', go.term='GO:0000151; …', structure.pdb.ids='8rs8; 4igk; …'
  NOTAREALGENE [unresolved] protein.name='', go.term='', structure.pdb.ids=''
```

Your terms and structures may differ: these sources are updated continuously.

Each input becomes one row, in the order you gave. TP53 and BRCA1 are `resolved`; the
made-up symbol is `unresolved`, which means the source found no match. It is kept in
the result, so you can report it rather than lose it silently.

## Look inside a row

A row is a dictionary keyed by field:

```python
tp53 = result["TP53"][0]
tp53["protein.name"]
```

```text
'Cellular tumor antigen p53'
```

The GO terms and structures are lists. Each one knows how big it is and whether you
have all of it:

```python
terms = tp53["go.term"]
len(terms), terms.total, terms.complete
```

```text
(131, 131, True)
```

So TP53 has 131 GO terms and you have every one of them. If a source had stopped
early, `complete` would be `False` and the list would display as, for example,
`25 of 321` or `25+`. A list behaves like any Python list: you can loop over it,
slice it or test membership.

```python
"GO:0006915" in terms   # apoptotic process
```

For rows that came back empty, the `missing` key lists what is absent:

```python
result["NOTAREALGENE"][0]["missing"]
```

```text
['protein.name', 'go.term', 'structure.pdb.ids']
```

## Make a table

Turn the result into a pandas DataFrame, one row per gene:

```python
table = result.to_pandas()
table[["input", "status", "protein.name", "go.term.total", "structure.pdb.ids.total"]]
```

```text
          input      status                                 protein.name  go.term.total  structure.pdb.ids.total
0          TP53    resolved                   Cellular tumor antigen p53          131.0                    321.0
1         BRCA1    resolved  Breast cancer type 1 susceptibility protein           78.0                     33.0
2  NOTAREALGENE  unresolved                                          NaN            NaN                      NaN
```

The `.total` columns give each list's size, so you can compare genes directly. To get
one row per GO term instead, explode the list:

```python
terms_long = result.to_pandas(explode="go.term")
terms_long[["input", "go.term"]].head()
```

From here it is ordinary pandas: group, filter or join with your own data.

## Save the result and cite the sources

Write the rows to a file you can share or open in a spreadsheet:

```python
result.to_csv("tp53_brca1.csv")
```

Every value came from a public database, and those databases ask to be cited.
`cite()` lists exactly the ones this result used:

```python
print(result.cite())
```

```text
- wwPDB / EMBL-EBI PDBe — https://www.ebi.ac.uk/pdbe (licensed CC0-1.0; citation requested). Cite: https://doi.org/10.1093/nar/gkz990.
- Gene Ontology / EMBL-EBI QuickGO — https://www.ebi.ac.uk/QuickGO (licensed CC-BY-4.0; attribution required). Cite: https://doi.org/10.1093/bioinformatics/btp536.
- UniProt Consortium — https://www.uniprot.org (licensed CC-BY-4.0; attribution required). Cite: …
```

## What you made

You found fields by meaning, looked up three genes across three databases in one
call, checked which ones resolved, read complete lists with their sizes, built a
table and listed the sources to cite.

Next:

- [Work in Python](../how-to/work-in-python.md): larger batches, sessions and a
  cache, ambiguous matches and exports.
- [What a result means](../explanation/result-meaning.md): what `resolved`,
  `unresolved` and a list's size do and do not establish.
- [Python API reference](../reference/python-api.md): every function and option.
