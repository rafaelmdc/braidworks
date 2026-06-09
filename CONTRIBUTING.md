# Contributing to Braidworks

## Development setup

Braidworks is a [`uv`](https://docs.astral.sh/uv/) workspace. One command sets up
everything:

```bash
uv sync --all-extras
```

## Testing

Tests are **per package**, and the working directory matters: `taxon_weaver`'s
suite imports fixtures via `from tests....`, which only resolves when pytest runs
from inside `weavers/taxon_weaver/`. Use the Makefile and you won't have to think about it:

```bash
make test          # both suites
make test-core     # braidworks-core only
make test-weaver   # taxon_weaver only
```

Equivalent raw commands:

```bash
cd braidworks-core && uv run --extra test python -m pytest -q
cd taxon_weaver    && uv run --extra test python -m pytest -q
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
make new-weaver    SPEC=path/to/weaver.spec.toml DEST=weavers/<db>weaver   # under weavers/, like weavers/taxon_weaver/
```

This stamps a complete package from a `weaver.spec.toml`; you then implement only
the `# TODO` backend spots. See [`weaverkit/README.md`](weaverkit/README.md) for
the toolkit and [AGENTS.md](AGENTS.md) for the Spec→Scaffold→Implement→Verify loop
and the boundaries. For a step-by-step build manual with per-module skeletons and a
done-checklist, see
[docs/weaver-implementation-guide.md](docs/weaver-implementation-guide.md); for
*which* databases to build next and the reachability model, see
[docs/weaver-roadmap.md](docs/weaver-roadmap.md). The manual shape, for reference:

1. **Create a workspace member** `my_weaver/` with its own `pyproject.toml`
   (depends on `braidworks-core` via `[tool.uv.sources] braidworks-core = { workspace = true }`)
   and add it to `members` in the root `pyproject.toml`.
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

## Data artifacts

Never commit taxonomy databases or taxdump archives — they are multi-GB and
git-ignored (`*.sqlite`, `taxdump.tar.gz`, `/data/`). See
[docs/database.md](docs/database.md) for building them.
