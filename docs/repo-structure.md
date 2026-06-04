# Repository Structure

Braidworks uses a `uv` workspace monorepo. All packages live in the same repo; local dependency resolution means no PyPI publish is needed during development.

## Layout

```
braidworks/
  pyproject.toml              workspace root — declares members + shared ruff/pytest config
  Makefile                    dev tasks: test, lint, fmt
  README.md  CONTRIBUTING.md
  docs/                       architecture, usage, database, repo-structure, implementation-plan
  braidworks-core/
    pyproject.toml
    src/braidworks/core/
      strand.py               Strand, StrandSet, MergePolicy
      capability.py           OutputGroup, Capability, WeaverManifest
      result.py               WeaveResult, WeaveStatus, CandidateResult
      weaver.py               BaseWeaver ABC, BackendStrategy (generic backend identity)
      braid.py                CapabilityInvocation, Braid, BackendPolicy, FallbackCondition
      cache.py                StrandCacheKey, StrandCache, InMemoryStrandCache
      registry.py             BraidRegistry
      planner.py              Braider
      executor.py             LocalExecutor, ReviewPolicy, ErrorPolicy, ExecutionResult
      factory.py              WeaverProvider, WeaverFactory (Layer 1 of the weaver factory)
      exceptions.py
    src/braidworks/testing/
      contract.py             WeaverOrderContractTests, CacheFingerprintTests (shipped mixins)
    tests/
  taxonweaver/
    pyproject.toml            depends on braidworks-core (workspace); adds rapidfuzz, httpx
    src/taxonweaver/          the Braidworks weaver layer
      weaver.py               NCBITaxonWeaver
      dispatch.py             BackendDispatchWeaver (backend selection + mapping)
      vocab.py                strand type IDs, capabilities, manifest
      intermediate.py         TaxonMatch / LineageEntry / CandidateMatch (neutral intermediate)
      mapper.py               TaxonMatch -> WeaveResult (single source of strand shape)
      factory.py              build_ncbi_weaver(config)  (Layer 2 builder)
      provider.py             NCBIWeaverProvider (Layer 1 conformance)
      backends/
        base.py               ResolutionBackend (implements BackendStrategy)
        local.py              LocalTaxonomyBackend (wraps TaxonomyResolverService)
        datasets_v2.py        DatasetsV2Backend (NCBI Datasets v2 REST)
    src/taxonomy_resolver/    resolver library, migrated from taxonbridge (service, build, fuzzy, …)
    src/taxonomy_tools/       CLI incl. `taxon-weaver build-db` (download + build the SQLite DB)
    tests/
  (future) braidworks-celery/   Celery executor backend
  (future) uniprot-weaver/      second weaver (proves the shared weaver toolkit for extraction)
```

## Key pyproject.toml snippets

**Workspace root:**
```toml
[tool.uv.workspace]
members = ["braidworks-core", "taxonweaver"]
```

**`braidworks-core/pyproject.toml`:**
```toml
[project]
name = "braidworks-core"
dependencies = ["networkx>=3.0"]
```

**`taxonweaver/pyproject.toml`:**
```toml
[project]
name = "taxonweaver"
dependencies = ["braidworks-core", "rapidfuzz>=3.0,<4.0", "httpx>=0.27"]

[project.scripts]
taxon-weaver = "taxonomy_tools.cli:main"   # `taxon-weaver build-db ...`

[tool.uv.sources]
braidworks-core = { workspace = true }

[tool.hatch.build.targets.wheel]
packages = ["src/taxonweaver", "src/taxonomy_resolver", "src/taxonomy_tools"]
```

## Release

Each package versions and publishes independently. `uv sync` at the repo root resolves everything locally during development.
