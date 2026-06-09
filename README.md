# Braidworks

Braidworks is a modular biological data-integration framework. Source-specific
**weavers** expose typed **capabilities**; Braidworks discovers and runs routes
between identifiers, records, and databases automatically — in batch, with
caching, and with human-review hooks for ambiguous results.

> You describe what data you *have* and what you *want*; Braidworks finds the
> path between them and runs it.

## How it works (one paragraph)

Every value is a typed `Strand`; a collection of strands for one entity is a
`StrandSet`. A **Weaver** declares `Capabilities` — which strand types it consumes
and produces. The `BraidRegistry` projects those declarations into a graph, the
`Braider` finds the shortest route from your available types to your target
types, and the `LocalExecutor` runs that route in batch through a `StrandCache`.
Ambiguous or low-confidence results are flagged for review instead of silently
propagating.

## Repository layout

This is a [`uv`](https://docs.astral.sh/uv/) workspace monorepo:

```
braidworks/
├── braidworks-core/     # framework: strands, capabilities, registry, braider, executor, cache, factory
├── weaverkit/           # toolkit to add a weaver deterministically (spec → scaffold → verify)
├── weavers/             # the weavers (auto-discovered by the workspace glob)
│   ├── taxon_weaver/    #   advanced reference: NCBI taxonomy (local SQLite + Datasets v2 API)
│   ├── example_weaver/  #   minimal reference: lookup over a bundled CSV
│   └── bacdive_weaver/  #   BacDive type-strain phenotypes
├── docs/                # architecture, usage, database setup, roadmap, guides
├── Makefile             # common dev tasks (test, lint, new-weaver, verify-weaver, index)
└── pyproject.toml       # workspace root
```

See [docs/repo-structure.md](docs/repo-structure.md) for the full tree.

## Install

```bash
uv sync --all-extras    # creates the workspace venv and installs every package
```

## Quickstart

Two backends ship for NCBI taxonomy. **The API backend needs no local data:**

```python
import asyncio
from braidworks.core import BraidRegistry, Braider, LocalExecutor, Strand, StrandSet
from taxon_weaver import build_ncbi_weaver

async def main():
    registry = BraidRegistry()
    registry.register(build_ncbi_weaver(enable_api=True))   # remote NCBI Datasets v2; zero setup

    braid = Braider(registry).plan(
        available_types=frozenset({"organism.name"}),
        target_types=frozenset({"ncbi.taxon.id", "ncbi.taxon.lineage"}),
    )
    sets = [StrandSet.from_strands("e1", [Strand("organism.name", "Homo sapiens")])]
    result = await LocalExecutor(registry).execute(braid, sets)
    for ss in result.resolved:
        print(ss.get("ncbi.taxon.id").value, ss.get("ncbi.taxon.lineage").value)

asyncio.run(main())
```

For the **local** backend you first build the SQLite taxonomy DB once — see
[docs/database.md](docs/database.md) — then `build_ncbi_weaver(db_path=...)`.
Full guide: [docs/usage.md](docs/usage.md).

## Development

```bash
make test     # run every package's test suite
make lint     # ruff across the workspace
make help     # list all tasks
```

Note: tests are per-package and the working directory matters — use `make test`
(or see [CONTRIBUTING.md](CONTRIBUTING.md)) rather than a bare `pytest` from the
repo root.

## Documentation

| Doc | What it covers |
|---|---|
| [docs/index.md](docs/index.md) | Concepts and the result model |
| [docs/usage.md](docs/usage.md) | Install → choose a backend → run |
| [docs/database.md](docs/database.md) | Building / acquiring the NCBI taxonomy DB |
| [docs/architecture.md](docs/architecture.md) | Core abstractions, contracts, design decisions |
| [docs/repo-structure.md](docs/repo-structure.md) | Full repository layout |
| [docs/implementation-plan.md](docs/implementation-plan.md) | Build order, deliverables, definition of done |
| [docs/weaver-roadmap.md](docs/weaver-roadmap.md) | Which weavers to build next + the reachability model |
| [docs/weaver-implementation-guide.md](docs/weaver-implementation-guide.md) | Step-by-step manual for building a weaver |
| [docs/keys-index.md](docs/keys-index.md) | Catalog of keys that flow between weavers (generated) |
| [AGENTS.md](AGENTS.md) | Contributor boundaries + the Spec→Scaffold→Implement→Verify loop |
| [weaverkit/README.md](weaverkit/README.md) | The spec/scaffold/conformance toolkit |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, testing, and how to add a new weaver |
