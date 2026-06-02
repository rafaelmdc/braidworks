# Repository Structure

Braidworks uses a `uv` workspace monorepo. All packages live in the same repo; local dependency resolution means no PyPI publish is needed during development.

## Layout

```
braidworks/
  pyproject.toml              workspace root — declares members, no src
  docs/
  braidworks-core/
    pyproject.toml
    src/braidworks/core/
      strand.py               Strand, StrandSet, MergePolicy
      capability.py           OutputGroup, Capability, WeaverManifest
      result.py               WeaveResult, WeaveStatus, CandidateResult
      weaver.py               BaseWeaver ABC
      braid.py                CapabilityInvocation, Braid, BackendPolicy, FallbackCondition
      cache.py                StrandCacheKey, StrandCache, InMemoryStrandCache
      registry.py             BraidRegistry
      planner.py              Braider
      executor.py             LocalExecutor, ReviewPolicy, ErrorPolicy, ExecutionResult
      exceptions.py
    tests/
  taxonweaver/
    pyproject.toml            depends on braidworks-core (workspace)
    src/taxonweaver/
      weaver.py               NCBITaxonWeaver
      service.py              TaxonomyResolverService  ← moved from taxonbridge
      ...                     remaining taxonbridge modules
    tests/
  (future) braidworks-celery/
    pyproject.toml
    src/braidworks_celery/
  (future) uniprot-weaver/
    pyproject.toml
    src/uniprot_weaver/
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
dependencies = ["braidworks-core", "rapidfuzz>=3.0,<4.0"]

[tool.uv.sources]
braidworks-core = { workspace = true }
```

## Release

Each package versions and publishes independently. `uv sync` at the repo root resolves everything locally during development.
