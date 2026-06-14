# Repository Structure

Braidworks is a [`uv`](https://docs.astral.sh/uv/) workspace monorepo. Every package
lives in the same repo and resolves against the others locally, so no PyPI publish is
needed during development.

## Layout

```
braidworks/
  pyproject.toml              workspace root — members glob + shared ruff/pytest config
  Makefile                    dev tasks: sync, test, lint, fmt, new-weaver, verify-weaver, index
  README.md  CONTRIBUTING.md  AGENTS.md
  docs/                       architecture, usage, database, roadmap, guides, generated indexes
  .github/workflows/ci.yml    lint + test on push/PR

  braidworks-core/            the domain-neutral framework (no real weavers here)
    src/braidworks/core/
      strand.py               Strand, StrandSet, MergePolicy
      capability.py           OutputGroup, Capability, WeaverManifest
      result.py               WeaveResult, WeaveStatus, CandidateResult
      weaver.py               BaseWeaver ABC, BackendStrategy
      backend.py              BackendBase (shared backend ABC)
      records.py              LookupRecord, ResolverRecord, MatchStatus, Candidate
      mapper.py               map_lookup / map_resolver (shared strand-shape source)
      dispatch.py             BackendDispatchWeaver (shared dispatch runtime)
      braid.py                CapabilityInvocation, Braid, BackendPolicy, FallbackCondition
      cache.py                StrandCacheKey, compute_cache_key, StrandCache, InMemoryStrandCache
      registry.py             BraidRegistry
      planner.py              Braider
      executor.py             LocalExecutor, ReviewPolicy, ErrorPolicy, ExecutionResult
      factory.py              WeaverProvider, WeaverFactory (Layer 1 of the weaver factory)
      localdb.py              ensure_local_db + generic bulk-DB acquisition plumbing
      exceptions.py
    src/braidworks/testing/
      contract.py             WeaverOrderContractTests, CacheFingerprintTests (shipped mixins)
    tests/

  weaverkit/                  the toolkit that makes adding a weaver deterministic
    src/weaverkit/
      spec.py                 weaver.spec.toml parsing + validation
      scaffold.py             `weaverkit new` — stamps a thin weaver package from a spec
      conformance.py          `weaverkit verify` + WeaverConformanceTests
      index.py                `weaverkit index` — cross-weaver key map
      keys.py                 SHARED_KEYS (join keys) + OUTPUT_KEYS (leaf-output catalog)
      cli.py
    docs/                     decisions, backlog, PITFALLS, implementing-backends
    tests/                    + tests/fixtures/ (worked lookup/resolver/bulk specs)

  weavers/                    every weaver package (auto-discovered by the members glob)
    taxon_weaver/             advanced reference: resolver, local SQLite + NCBI API, bulk DB
    example_weaver/           minimal reference: lookup over a ~5-row bundled CSV
    uniprot_weaver/           the hinge: protein query -> UniProt entry (+ ncbi.taxon.id)
    pdbe_weaver/              protein -> experimental PDB structures (+ describe one)
    alphafold_weaver/         protein -> predicted-structure model metadata
    quickgo_weaver/           protein -> GO terms by aspect (+ describe one)
    reactome_weaver/          protein -> pathways participated in (+ describe one)
    string_weaver/            protein -> interaction partners (STRING network)
    bacdive_weaver/           organism -> BacDive type-strain phenotypes
    disbiome_weaver/          organism (taxid) -> microbe-disease associations
  braidworks-arq/             optional: distributed execution over arq/Redis
```

(Run `make index` for the always-current map: `docs/weavers-index.tsv` +
`docs/keys-index.md`.)

Each weaver package has the same shape:

```
weavers/<db>_weaver/
  pyproject.toml              depends on braidworks-core (workspace)
  Makefile                    test / test-live / lint / fmt (+ ensure if it has a local DB)
  weaver.spec.toml            the contract — source of truth for the manifest
  src/<db>_weaver/
    vocab.py                  type IDs, capabilities, manifest (generated from the spec)
    factory.py                build_<db>_weaver() (Layer 2) + provider
    backends/                 one module per data source (local / api), the # TODO spots
  tests/                      unit + contract mixins + opt-in live E2E
```

`taxon_weaver` is the exception — it brings its own `dispatch.py` / `mapper.py` /
`intermediate.py` and a hand-written `vocab.py` (the "bring your own plumbing"
reference), and also carries `src/taxonomy_resolver/` (the resolver library migrated
from taxonbridge) and `src/taxonomy_tools/` (the `taxon-weaver` CLI).

## Key `pyproject.toml` snippets

**Workspace root:**
```toml
[tool.uv.workspace]
members = ["braidworks-core", "weaverkit", "weavers/*"]
```
The `weavers/*` glob means a newly scaffolded weaver is part of the workspace with no
root edit. (Corollary: keep a `weaver.spec.toml` *outside* `weavers/` until you
scaffold — a spec-only dir there has no `pyproject.toml` and breaks `uv`.)

**A weaver package:**
```toml
[project]
name = "<db>_weaver"
dependencies = ["braidworks-core", "httpx>=0.27"]   # +rapidfuzz for resolvers

[tool.uv.sources]
braidworks-core = { workspace = true }
```

## Release

Each package versions independently; `uv sync` at the repo root resolves everything
locally during development.
