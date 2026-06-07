# exampleweaver — the canonical reference weaver

The **minimal, fully-implemented** Braidworks weaver: `ncbi.taxon.id → microbe
traits`, served from a ~5-row CSV bundled in the package. It is small on purpose —
read it end-to-end in a minute, then copy the shape for your own weaver.

It is literally what `weaverkit new` produces with the three backend `# TODO`s
filled in, so it passes the full bar:

```bash
make test                                              # conformance + contract + golden
uv run weaverkit verify --spec weaver.spec.toml \
    --package exampleweaver --strict                   # definition-of-done: complete
```

- **The contract:** [`weaver.spec.toml`](weaver.spec.toml).
- **The one file to copy:** [`src/exampleweaver/backends/local.py`](src/exampleweaver/backends/local.py)
  — a real `fetch` / `fingerprint` / `is_configured` over the bundled CSV.
- **The data:** [`src/exampleweaver/data/example_traits.csv`](src/exampleweaver/data/example_traits.csv).
- **Per-function contracts:** [weaverkit/docs/implementing-backends.md](../weaverkit/docs/implementing-backends.md).

This is the *minimal* reference (a `lookup` weaver). For the *advanced* case — a
`resolver` with fuzzy matching, two backends, and a multi-GB bulk DB — see
`taxonweaver/`.

## Registering it

```python
from braidworks.core import WeaverFactory
import exampleweaver

factory = WeaverFactory()
exampleweaver.register(factory)        # makes "example" buildable by the braider
```
