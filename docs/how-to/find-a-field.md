# Find a field and preview its route

Find the field names to pass as `--have` and `--want`, and check that the installed
sources can connect them before fetching anything.

## Search by meaning

```bash
uv run braidworks find pdb structures
```

`find` ranks the installed fields against plain words, best match first, and shows what
each means, which source provides it and what it starts from. Use a match as `--want`,
or as `--have` when it is something you supply. `--format json` or `--format tsv` gives
the same matches for scripts; Python's `bw.find("pdb structures")` ranks identically.
If nothing matches, try other words or list every field with `braidworks keys`.

## See who produces or consumes a field

```bash
uv run braidworks keys --produces structure.pdb.ids
uv run braidworks weavers
```

`keys` shows which sources produce or consume a field; `weavers` lists each installed
capability with its parameters. The [key index](../reference/keys-index.md) covers the
repository's full catalogue, including sources you have not installed.

## Preview a route without fetching

```bash
uv run braidworks path --from protein.query --to structure.pdb.ids
```

`path` prints the steps a query would take. When there is no route, the message names
the input or output nothing installed handles, suggests close field names and says
which missing source would handle it. Then [run the query](run-queries.md).
