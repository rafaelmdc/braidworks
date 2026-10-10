# example_weaver — the canonical reference weaver

The **minimal, fully-implemented** Braidworks weaver: `ncbi.taxon.id → microbe traits`,
served from a ~5-row CSV bundled in the package. It is small on purpose — read it
end-to-end, then use the Spec → Scaffold → Implement → Verify loop for your own
weaver. It follows the generated lookup architecture, with a worked CSV backend
and deliberate removal of the discovery entry point. It passes the full `--strict` bar.

- **Source:** bundled sample data · **License:** CC0-1.0 · **Backend:** `local` (bundled CSV)
- A teaching reference: it has **no `braidworks.weavers` entry point**, so it isn't
  auto-discovered by the `braidworks` CLI — build it directly in code.

## Capabilities

| Capability | Input types | Output groups / expandable keys | Backends | Parameters |
|---|---|---|---|---|
| `describe_traits` | `ncbi.taxon.id` | `traits.core`, `traits.growth` | `local` | — |

These are the current declared capabilities. Output groups select fields computed
together; expandable keys identify related entities you can follow. See
[the spec](weaver.spec.toml) for exact output fields and parameter defaults, or
`braidworks weavers` for the installed inventory. Backend declarations do not imply
that optional local data are already configured.

## The files to copy

- **The contract:** [`weaver.spec.toml`](https://github.com/rafaelmdc/braidworks/blob/main/weavers/example_weaver/weaver.spec.toml).
- **The one file to copy:** [`src/example_weaver/backends/local.py`](https://github.com/rafaelmdc/braidworks/blob/main/weavers/example_weaver/src/example_weaver/backends/local.py)
  — a real `fetch` / `fingerprint` / `is_configured` over the bundled CSV.
- **The data:** [`src/example_weaver/data/example_traits.csv`](https://github.com/rafaelmdc/braidworks/blob/main/weavers/example_weaver/src/example_weaver/data/example_traits.csv).
- **Per-function contracts:** [weaverkit/docs/implementing-backends.md](https://github.com/rafaelmdc/braidworks/blob/main/weaverkit/docs/implementing-backends.md).

## Complete offline batch example

```python
import asyncio
from braidworks.core import Strand, StrandSet
from example_weaver import build_example_weaver


async def main():
    inputs = [
        StrandSet.from_strands(f"sample-{i}", [Strand("ncbi.taxon.id", taxid)])
        for i, taxid in enumerate(["562", "1423", "999999999", "562"])
    ]
    async with build_example_weaver() as weaver:
        results = await weaver.execute_batch(
            "describe_traits",
            inputs,
            requested_outputs=frozenset({"microbe.trait.gram_stain"}),
            backend="local",
        )
        for result in results:
            print(result.to_json())


asyncio.run(main())
```

This returns four results in input order: negative, positive, a `NO_MATCH`, and
negative again. Only the requested gram-stain output is emitted; duplicates retain
separate input identities. Request `microbe.trait.optimum_temp` for the growth group.
Temperatures are string values in degrees Celsius. These five illustrative rows
are teaching data, not a strain-specific, experimentally validated trait database.

The backend loads and privately caches the bundled CSV; a private pure parser
validates exactly three unique headers, row width and unique positive taxids
(normalized to decimal IDs). Column order is flexible; blank trait cells mean
absent values. A malformed source yields per-input errors rather than false misses.
The backend maps columns to output keys and
copies each row into the result so callers cannot mutate cached data. Neither
group requires expensive work, so it computes both fields and lets the core mapper
filter requested outputs. Change `DATA_VERSION` whenever the bundled data changes.

For explicit provider registration, call `example_weaver.register(factory)` on a
`WeaverFactory`. This package intentionally has no CLI discovery entry point.

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

## Construction and resource lifetime

Supported builder options are explicit; unknown options raise
`BackendConfigurationError`. Empty construction remains safe for discovery.
See [configuration and lifetime](../../docs/weaver-configuration.md) for provider
configuration, source selection and owned/borrowed HTTP clients. Use
`async with weaver:` or `await weaver.aclose()` after requests finish.
