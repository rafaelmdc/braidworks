# Case studies

Three worked analyses, each a notebook that installs Braidworks, records its
environment (date, Python, package versions), times the lookup cold and with a warm
lookup cache, and saves a table (CSV), the full result and a figure (PNG and SVG) in
`case-study-output/`. Open one in Colab from its badge, or run it in Jupyter.

| Notebook | Question | Sources | Cold / warm (one run, 2026-11-09) |
|---|---|---|---|
| [Cancer gene structures](cancer-gene-structures.ipynb) | Experimental structures, AlphaFold confidence and Reactome pathways for 20 cancer genes | UniProt, PDBe, AlphaFold DB, Reactome | 11.7 s / 0.07 s |
| [Microbial functional groups](microbial-functional-groups.ipynb) | FAPROTAX functional groups of 10 environmental genera | NCBI Taxonomy, FAPROTAX | 2.2 s / 0.05 s |
| [Gut microbe–disease associations](gut-microbe-disease-associations.ipynb) | Diseases with a reported association for 6 gut species | NCBI Taxonomy, Disbiome (local database, built on first run in about 4 s) | 0.06 s / 0.02 s |

The timings come from one run on a workstation with a broadband connection. In that
run, NCBI answered from a local taxonomy database; on a fresh machine it uses the web
API, so expect the second and third cold times to be longer. The sources are live
databases: counts drift as they are updated, so compare a rerun with the environment
record it saves, not with these numbers.

The notebooks install from PyPI, so they need the first package release.
