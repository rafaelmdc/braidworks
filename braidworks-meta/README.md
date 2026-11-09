# braidworks

Installs Braidworks with every public source and the browser interface:

```bash
pip install braidworks          # or: uv tool install braidworks
braidworks get TP53 --want protein.name --param organism=9606
braidworks serve                # the browser interface
```

Or run it once without installing: `uvx braidworks get TP53 --want protein.name`.

This package contains no code. It depends on `braidworks-core` (the planner, the
`braidworks` command and the Python API), `weaverkit[serve]` (the browser server) and
one package per source. To install fewer sources, install `braidworks-core` with the
source packages you need instead. `pip install "braidworks[pandas]"` adds pandas for
`Result.to_pandas()`.

Documentation: https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md
