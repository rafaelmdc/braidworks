# Reference

Use these pages to look up interfaces, output shapes and operational contracts.
For a first exercise, start with [tutorials](../index.md#learn-through-a-tutorial).
For task instructions, use [the documentation index](../index.md).

| Subject | Reference |
|---|---|
| CLI commands and options | `braidworks --help`, `braidworks weave --help`, and each subcommand's `--help` |
| Installed capabilities and parameters | `braidworks weavers`; source READMEs/specs linked from [the catalogue](../sources.md) |
| Source purposes and setup requirements | [Source catalogue](../sources.md) |
| Inputs, outputs and producer/consumer connections | [Generated key index](../keys-index.md) |
| Machine exports, Python result objects and run archives | [Result reference](results.md) |
| Cache defaults, storage schemas, leases and retention | [Storage reference](persistence.md) |
| Builder configuration and client lifetime | [Weaver configuration](../weaver-configuration.md) |
| Core invariants for adapter authors | [Core contracts](../core-contracts.md) |
| Weaver spec fields | [Toolkit spec reference](../../weaverkit/README.md#weaverspectoml-field-reference) |
| Backend fetch, configuration and fingerprints | [Backend reference](../../weaverkit/docs/implementing-backends.md) |

For Python query construction, the [fetch interface](../../braidworks-core/src/braidworks/core/fetch.py)
and [explicit query service](../../braidworks-core/src/braidworks/core/query.py) define
signatures and contracts. [Python usage](../usage.md#query-from-python) provides executable
examples. This landing page links current authorities; it does not duplicate their
full signatures or claim a generated API reference exists.
