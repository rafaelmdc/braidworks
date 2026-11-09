# Reference

Use these pages to look up interfaces, output shapes and operational contracts.
For a first exercise, start with [tutorials](../index.md#learn-through-a-tutorial).
For task instructions, use [the documentation index](../index.md).

| Subject | Reference |
|---|---|
| Python API: `get`, `Session`, `Result`, `Listing` | [Python API reference](python-api.md) (generated from docstrings) |
| CLI commands and options | [CLI reference](cli/index.md): one page per command, generated from `--help` |
| Installed capabilities and parameters | `braidworks weavers`; source READMEs/specs linked from [the catalogue](sources.md) |
| Source purposes and setup requirements | [Source catalogue](sources.md) |
| Inputs, outputs and producer/consumer connections | [Generated key index](keys-index.md) |
| Exceptions, failure values and diagnostic categories | [Failure contract](failures.md) |
| Machine exports, Python result objects and run archives | [Result reference](results.md) |
| Cache defaults, storage schemas, leases and retention | [Storage reference](persistence.md) |
| Local source generations, locks and NCBI reviewed history | [Local-data reference](local-data.md) |
| HTTP accounting, defaults and coordination | [Pacing reference](request-pacing.md) |
| Strict/tolerant plugin loading | [Discovery reference](discovery.md) |
| Browser HTTP execution and generated artifacts | [Browser reference](browser.md) |
| Builder configuration and client lifetime | [Weaver configuration](weaver-configuration.md) |
| Core invariants for adapter authors | [Core contracts](core-contracts.md) |
| Weaver spec fields | [Toolkit spec reference](../../weaverkit/docs/spec-reference.md) |
| Scaffold generation, validation and writing | [Scaffold interfaces](../../weaverkit/docs/scaffold-reference.md) |
| Backend fetch, configuration and fingerprints | [Backend reference](../../weaverkit/docs/implementing-backends.md) |

The [Python API reference](python-api.md) is generated from the public docstrings
(`make api-docs`; `make docs-check` rejects drift). [Work in Python](../how-to/work-in-python.md)
provides executable recipes. Lower-level engine contracts are in
[core contracts](core-contracts.md); `fetch` remains for existing scripts.
