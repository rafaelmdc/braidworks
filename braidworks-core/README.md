# braidworks-core

Core provides the domain-neutral data model, planner, executor, source discovery and
`braidworks` query CLI. Biological adapters live in separate weaver packages and join
through registered input/output types. Runtime dependencies are networkx for routing
and platformdirs for local paths.

## Query and inspect sources

Install core with the weavers your analysis needs. Start with [installation](../docs/installation.md)
and [query usage](../docs/usage.md), or follow a [researcher tutorial](../docs/index.md#learn-through-a-tutorial).
The CLI plans across sources with `weave`, calls one capability with `run`, and exposes
inventory, keys, paths and references through its inspection commands.

Use `fetch`/`async_fetch` for ordinary Python lookups. Applications needing configured
registries, expansion or managed execution can use the explicit query service;
[Python usage](../docs/usage.md#query-from-python) includes complete examples.

## Concepts and exact contracts

| Component | Responsibility |
|---|---|
| `Strand`, `StrandSet` | Typed values and the values belonging to one input entity |
| `Capability`, `WeaverManifest` | Declared inputs, outputs, groups, parameters and backend availability |
| `BraidRegistry`, `Braider` | Registered sources and routes between types |
| `LocalExecutor` | Batched execution, caching, review and related-entity expansion |
| `ExecutionResult`, `FetchResult` | Outcomes, retained values and coverage |

Read [architecture](../docs/architecture.md) for how these pieces fit together.
Use [core contracts](../docs/core-contracts.md) and [the reference index](../docs/reference/index.md)
for interfaces and invariants. [Discovery reference](../docs/reference/discovery.md)
describes strict/tolerant loading and its failure report.

## Saved observations and progress

Caching and durable run storage are opt-in. Use [cache and saved-run tasks](../docs/persistence.md)
to configure local paths and continue work; [storage reference](../docs/reference/persistence.md)
retains TTLs, leases, ownership and compatibility rules. Observation archives are
separate exports; see [export tasks](../docs/results.md) and [archive reference](../docs/reference/results.md#run-archives).

## Contribute and license

Run `make test-core` from the workspace root. Follow [contributing](../CONTRIBUTING.md)
and [repository rules](../AGENTS.md); package-index availability is not assumed.
The software uses [MIT](LICENSE). Provider data and samples retain their own licenses
and attribution requirements as declared by each weaver.
