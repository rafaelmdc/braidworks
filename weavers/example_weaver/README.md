# example_weaver — the canonical reference weaver

The **minimal, fully-implemented** Braidworks weaver: `ncbi.taxon.id → microbe traits`,
served from a ~5-row CSV bundled in the package. It is small on purpose — read it
end-to-end in a minute, then copy the shape for your own weaver. It is literally what
`weaverkit new` produces with the three backend `# TODO`s filled in, so it passes the full
`--strict` bar.

- **Source:** bundled sample data · **License:** CC0-1.0 · **Backend:** `local` (bundled CSV)
- A teaching reference: it has **no `braidworks.weavers` entry point**, so it isn't
  auto-discovered by the `braidworks` CLI — build it directly in code.

## Capabilities

| Capability | Consumes | Produces (by group) |
|---|---|---|
| `describe_traits` | `ncbi.taxon.id` | **traits.core:** `microbe.trait.gram_stain` · **traits.growth:** `microbe.trait.optimum_temp` |

## The files to copy

- **The contract:** [`weaver.spec.toml`](https://github.com/rafaelmdc/braidworks/blob/main/weavers/example_weaver/weaver.spec.toml).
- **The one file to copy:** [`src/example_weaver/backends/local.py`](https://github.com/rafaelmdc/braidworks/blob/main/weavers/example_weaver/src/example_weaver/backends/local.py)
  — a real `fetch` / `fingerprint` / `is_configured` over the bundled CSV.
- **The data:** [`src/example_weaver/data/example_traits.csv`](https://github.com/rafaelmdc/braidworks/blob/main/weavers/example_weaver/src/example_weaver/data/example_traits.csv).
- **Per-function contracts:** [weaverkit/docs/implementing-backends.md](https://github.com/rafaelmdc/braidworks/blob/main/weaverkit/docs/implementing-backends.md).

```python
from example_weaver import build_example_weaver

weaver = build_example_weaver()        # zero-config, offline
# In an app that wires a WeaverFactory, `example_weaver.register(factory)` adds it as a provider.
```

```bash
make test                                              # conformance + contract + golden
uv run weaverkit verify --spec weaver.spec.toml \
    --package example_weaver --strict                   # definition-of-done: complete
```

This is the *minimal* reference (a `lookup` weaver). For the *advanced* case — a
`resolver` with fuzzy matching, two backends, and a multi-GB bulk DB — see
[`../ncbi_weaver/`](https://github.com/rafaelmdc/braidworks/blob/main/weavers/ncbi_weaver). Build loop & boundaries: [AGENTS.md](https://github.com/rafaelmdc/braidworks/blob/main/AGENTS.md).

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/weavers/example_weaver/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.
