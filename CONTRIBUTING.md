# Contributing to Braidworks

## Development setup

Braidworks is a [`uv`](https://docs.astral.sh/uv/) workspace. One command sets up
everything:

```bash
uv sync --all-extras
```

## Testing

Tests are **per package**, and the working directory matters: a weaver's suite
imports fixtures via `from tests....`, which only resolves when pytest runs from
inside the package dir. Use the Makefile and you won't have to think about it:

```bash
make test          # every package's suite (core + weaverkit + every weaver)
make test-core     # braidworks-core only
make test-kit      # weaverkit only
make test-weavers  # every weaver under weavers/* (auto-discovered)
```

Equivalent raw command (per package):

```bash
cd braidworks-core      && uv run --extra test python -m pytest -q
cd weavers/taxon_weaver && uv run --extra test python -m pytest -q
```

A bare `pytest` (or `uv run pytest`) from the repo root will pick up the root
pytest config and run only the core suite — prefer `make test`.

## Linting

```bash
make lint     # ruff check
make fmt      # ruff format
```

CI runs `make lint` and `make test`; keep both green.

## Conventions

- **Python 3.12+**, line length 100 (see root `pyproject.toml`).
- Every dataclass on a public boundary round-trips through `to_json()` /
  `from_json()`.
- Failures are *values* (`WeaveStatus.NO_MATCH` / `ERROR`), not exceptions,
  except for structural problems (`BackendConfigurationError`,
  `InvalidManifestError`).
- Keep `braidworks-core` domain-neutral — no taxonomy/resolution assumptions.

## Adding a new weaver

Weavers follow a consistent shape so they plug into the framework uniformly. The
deterministic path is **not** copying files by hand — use the scaffold generator:

```bash
make verify-weaver SPEC=path/to/weaver.spec.toml          # validate the spec
make new-weaver    SPEC=path/to/weaver.spec.toml DEST=weavers/<db>_weaver   # under weavers/, like weavers/taxon_weaver/
```

This stamps a complete package from a `weaver.spec.toml`; you then implement only
the `# TODO` backend spots. See [`weaverkit/README.md`](weaverkit/README.md) for
the toolkit and [AGENTS.md](AGENTS.md) for the Spec→Scaffold→Implement→Verify loop
and the boundaries. For a step-by-step build manual with per-module skeletons and a
done-checklist, see
[docs/weaver-implementation-guide.md](docs/weaver-implementation-guide.md); for
*which* databases to build next and the reachability model, see
[docs/weaver-roadmap.md](docs/weaver-roadmap.md). The manual shape, for reference:

1. **Create the package** at `weavers/<db>_weaver/` with its own `pyproject.toml`
   (depends on `braidworks-core` via `[tool.uv.sources] braidworks-core = { workspace = true }`).
   The root `members = ["braidworks-core", "weaverkit", "weavers/*"]` glob picks it up
   automatically — no root edit needed.
2. **Define a neutral intermediate** — a small dataclass your backends normalize
   their native responses into (taxon_weaver's is `TaxonMatch`). Keep it in your
   package; never leak it into core.
3. **Write one mapper** `intermediate -> WeaveResult`. A single mapper is what
   guarantees every backend emits identical strand shapes.
4. **Implement one or more backends** as `ResolutionBackend`-style classes that
   satisfy core's `BackendStrategy` (`name`, `is_configured()`, `fingerprint()`)
   plus your domain operation. One per data source (e.g. local DB, REST API).
5. **Assemble** with a `BackendDispatchWeaver` subclass that holds
   `{backend_name: backend}`, declares a `MANIFEST` for the backends actually
   wired in, and dispatches `execute_batch`.
6. **Provide the factory glue** (Layer 2 — only your package knows how to
   construct its backends), following the **two-builder convention**:
   - `build_<package>()` — a zero-config *introspection* builder (backends present,
     possibly unconfigured) that `weaverkit verify` calls;
   - a domain-named *configured* builder (e.g. `build_my_weaver(...)`) for real use,
     which may raise if nothing is usable;
   - a `WeaverProvider` (`weaver_id`, `build(config)`) wrapping it (Layer 1
     conformance), so it can be registered in a `WeaverFactory`.
7. **Ship contract tests.** Subclass `WeaverOrderContractTests` and
   `CacheFingerprintTests` from `braidworks.testing.contract`, once per backend.

See [docs/architecture.md](docs/architecture.md) ("Backend strategies and
dispatch" and "Weaver assembly: the two-layer factory") for the rationale.

## Versioning & backwards compatibility

Each package versions and releases **independently** (`braidworks-core`,
`weaverkit`, and every `weavers/*`). They are tagged per package, not as one repo
version:

```
braidworks-core-v0.1.0
taxon_weaver-v0.1.0
bacdive_weaver-v0.1.0
```

Weavers (and `weaverkit`) depend on the core with a **floor, not a ceiling** —
`braidworks-core>=0.1.0`, no upper bound. The contract is:

- **`braidworks-core` keeps backwards compatibility by default.** A new core
  release must not break the public surface weavers build on (`Strand`,
  `WeaveResult`, `LookupRecord`/`ResolverRecord`, `BackendDispatchWeaver`,
  `map_lookup`/`map_resolver`, the manifest/capability types).
- **If a core change *must* break compatibility,** bump the floor in every weaver
  that needs the new behaviour (`braidworks-core>=X.Y.0`) in the same change, and
  call out the break in the core release notes. The `>=` floor is what lets us find
  and update those weavers.
- The `[tool.uv.sources] braidworks-core = { workspace = true }` entry only governs
  local development; the `[project.dependencies]` floor is what a built/published
  artifact carries.

## Data artifacts

Never commit taxonomy databases or taxdump archives — they are multi-GB and
git-ignored (`*.sqlite`, `taxdump.tar.gz`, `/data/`). See
[docs/database.md](docs/database.md) for building them.
