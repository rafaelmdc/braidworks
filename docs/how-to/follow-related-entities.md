# Follow related entities from the command line

Turn a list of related IDs (every structure of a protein, every ortholog of a gene) into
one row per related entity, then look up details for each. This guide assumes you can
already [run a single query](run-queries.md).

## Get details for every member of a list

Listing structure IDs gives one collection. To retrieve the title and method of each
structure, expand the IDs into separate child rows:

```bash
uv run braidworks get P04637 --have protein.query \
    --want structure.pdb.title,structure.pdb.method --expand all --format tsv
```

`--expand all` follows every returned member within the expansion budget;
`--expand top:5` follows up to five in the source's order. With the default `none`, a
list you ask for directly comes back whole on one row (for example every GO term or PDB
ID); a list that only connects to a later lookup uses the source's first member, with a
warning. Expansion follows related IDs; ambiguous matches still pause for review.

## Follow a relationship that returns the same kind of entity

For relationships whose results are the same type as their input, such as orthologs,
use `--for-each`. With `ncbi_weaver` installed, this follows TP53's primate orthologs:

```bash
uv run braidworks get --have gene.ncbi.id=7157 --for-each orthologs \
    --param taxon_filter=9443 --want gene.symbol,gene.organism --format tsv
```

Without `--want`, each row shows the key it was reached through (here `gene.ncbi.id`).
When a relationship name is ambiguous, name the capability with `--traverse`, for
example `--traverse ncbi.list_orthologs`. A traversal implies `--expand all`.

## Limit and check the expansion

`--max-expansion N` sets one run-wide budget of rows (default 10,000), counted across
every chunk and traversal. Original inputs are always kept. When the budget cuts a list
short, stderr reports `kept K of N` for the affected row, and `--format json` records it
under `result.truncations`; check for it when your analysis needs every member.

Each child row carries `parent` (the input it came from) and `row` (that input's
position), so you can regroup children with their inputs; see
[reading results](check-results.md).
