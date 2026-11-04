# Find your way around the repository

Braidworks is a `uv` workspace. Packages resolve against each other locally during
development and have independent release versions. This map is for contributors;
[architecture](architecture.md) explains responsibilities and [contributing](../CONTRIBUTING.md)
covers setup and verification.

## Package map

```text
braidworks/
├── braidworks-core/     Domain-neutral framework and query CLI
├── weavers/             Biological source adapters, one package per source
├── weaverkit/           Specs, scaffolds, verification, catalogues, browser
├── braidworks-arq/      Experimental distributed executor
├── examples/            Small example input files
├── docs/                User guides, reference, and separate design/audit history
├── tools/               Release checks and development utilities
├── .github/workflows/   CI and release workflows
├── pyproject.toml       Workspace membership and shared tooling configuration
└── Makefile             Commands that run suites from their required directories
```

`pyproject.toml` lists core, toolkit, arq, and `weavers/*` as members. A new scaffold
under `weavers/` is picked up without a root edit. Keep a new spec outside that directory
until scaffolding creates its package metadata; a spec-only directory breaks workspace
resolution.

## Where to change code

| Change | Start here |
|---|---|
| Public values, capability declarations, and result shapes | [core package](../braidworks-core/src/braidworks/core/) |
| Discovery, query orchestration, or CLI behavior | `discovery.py`, `query.py`, `cli.py` in core |
| Routing and execution | `registry.py`, `planner.py`, `executor.py` in core |
| Lookup caches or saved runs | Core persistence modules; [storage guide](persistence.md) |
| Provider API or local-data behavior | `weavers/<source>_weaver/src/<source>_weaver/` |
| New-weaver generation and verification | [weaverkit source](../weaverkit/src/weaverkit/) |
| Browser routes or interface | `weaverkit` server modules and static assets |
| Release artifacts and checks | [tools](../tools/) and [release guide](releasing.md) |

## Weaver package shape

```text
weavers/<source>_weaver/
├── weaver.spec.toml     Manifest source of truth
├── pyproject.toml      Package version, dependencies, discovery entry point
├── src/<source>_weaver/
│   ├── vocab.py         Generated capability/type declarations
│   ├── factory.py       Builders and provider configuration
│   ├── weaver.py        Shared-dispatch assembly for scaffolded weavers
│   └── backends/        Provider-specific fetching and normalization
├── tests/              Unit, contract, golden, and opt-in live checks
├── README.md           Use, setup, interpretation, and citations
├── CONTRIBUTING.md     How to extend this adapter
└── Makefile            Package-specific test and verification commands
```

Local-data adapters may add setup/build modules and fixtures. NCBI retains custom
records, mapping, dispatch, and hand-written vocabulary; it is not the template to
copy wholesale for a new adapter. Use the [scaffold loop](../weaverkit/README.md).

Generated vocabulary is reviewed through safe regeneration; do not hand-edit it
except for the documented NCBI exception. See [repository rules](../AGENTS.md).
CI runs on pull requests and pushes to `main`; a push to another branch alone does
not run that workflow. Use Makefile targets for cwd-sensitive package suites.
