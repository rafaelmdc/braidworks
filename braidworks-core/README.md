# braidworks-core

The domain-neutral framework at the centre of Braidworks: the data model, the planner,
the executor, weaver discovery, and the `braidworks` command-line interface. Runtime dependencies are `networkx` (routing) and
`platformdirs` (user cache paths). **No real weavers live here** — they're separate packages that plug in via
the `braidworks.weavers` entry point.

## Concepts

| Abstraction | What it is |
|---|---|
| `Strand` | one typed fact (`type_id` + value), e.g. `protein.query = "P04637"` |
| `StrandSet` | all the strands for one entity, threaded through a run |
| `Capability` / `WeaverManifest` | a weaver's typed declaration of what it consumes → produces (with `set_outputs` for one→many fan keys) |
| `BraidRegistry` | the set of registered weavers, projected into a type→type graph |
| `Braider` | the planner: finds a route from the types you have to the types you want |
| `LocalExecutor` | runs a plan in batch, with caching, review hooks, and fan-out (`ExpandPolicy`) |
| `ExecutionResult` | the outcome, bucketed into `resolved` / `unresolved` / `review_queue` |

Discovery (`build_registry_from_entry_points`) loads every installed weaver from the
`braidworks.weavers` entry-point group, so the CLI and an arq worker share one mechanism.

## The `braidworks` CLI

Installing this package puts a `braidworks` command on your PATH — query and inspect the
weaver network from the shell (`weave`, `run`, `weavers`, `keys`, `path`, `references`).
See the [top-level README](https://github.com/rafaelmdc/braidworks/blob/main/README.md#2-ask-a-question--from-the-shell) and
[docs/usage.md](https://github.com/rafaelmdc/braidworks/blob/main/docs/usage.md).

## Python API

```python
from braidworks.core import BraidRegistry, Braider, LocalExecutor, Strand, StrandSet

registry = BraidRegistry()
registry.register(some_weaver)                     # or build_registry_from_entry_points()
braid = Braider(registry).plan(
    available_types=frozenset({"protein.query"}),
    target_types=frozenset({"protein.name"}),
)
result = await LocalExecutor(registry).execute(braid, strand_sets)
```

Design rationale and the full contract: [docs/architecture.md](https://github.com/rafaelmdc/braidworks/blob/main/docs/architecture.md).
Tests: `make test-core` (or `cd braidworks-core && uv run --extra test pytest`).

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/braidworks-core/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.


For inspectable CLI run records, add `--archive run.json` to `braidworks weave` or
`braidworks run`. It saves inputs, settings, outcomes, fingerprints and citations in
a new JSON file. See the [archive and restart scope](https://github.com/rafaelmdc/braidworks/blob/main/docs/usage.md#save-a-run-archive).
