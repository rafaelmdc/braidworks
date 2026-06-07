# AGENTS.md — working in Braidworks

Instructions for an AI agent (or human) contributing to this repository. Read this
before making changes. It is intentionally short and prescriptive; the deeper
"why" lives in `docs/`.

## What this repo is

Braidworks is a `uv` workspace of composable biological data resolvers called
**weavers**. `braidworks-core` is the domain-neutral framework; each weaver (e.g.
`taxonweaver`) wraps one data source. `weaverkit` is the toolkit that makes adding
a weaver deterministic rather than improvised.

## Commands

```bash
make sync                 # set up the venv (uv sync --all-extras)
make test                 # run every package's suite (core + weavers + weaverkit)
make lint                 # ruff check across all packages
make fmt                  # ruff format

# adding a weaver:
make new-weaver  SPEC=path/to/weaver.spec.toml DEST=weavers/<db>weaver
make verify-weaver SPEC=path/to/weaver.spec.toml PACKAGE=<db>weaver
```

CI runs `make lint` and `make test`; both must stay green.

## Adding a weaver: the Spec → Scaffold → Implement → Verify loop

Do **not** hand-write a weaver from scratch. Follow the loop:

1. **Spec.** Write a `weaver.spec.toml` (see `weaverkit/tests/fixtures/` for a
   complete example, and `docs/weaver-implementation-guide.md` for each field).
   Pick `consumes` from the **shared-key registry** (`weaverkit/src/weaverkit/keys.py`)
   so the weaver is reachable, and set `kind` (`lookup` for clean ID→data, the
   default; `resolver` for fuzzy/ambiguous name matching — it generates the richer
   candidate/`MatchStatus` shape). Validate it: `make verify-weaver SPEC=... ` —
   it reports every problem at once.
2. **Scaffold.** `make new-weaver SPEC=... DEST=weavers/<db>weaver`. This stamps a
   complete, importable package whose manifest already matches the spec and whose
   conformance test is wired up. Add the new package to `members` in the root
   `pyproject.toml`, then `make sync`.
3. **Implement.** The only edits you should need are the spots marked `# TODO`:
   each backend's `fetch` (currently `NotImplementedError`) and its `fingerprint`
   (currently a placeholder). Normalize each source result into the generated
   `*Record` intermediate; the shared mapper turns it into strands. Add real
   golden examples to the spec.
4. **Verify.** `make verify-weaver SPEC=... PACKAGE=<db>weaver` and
   `cd weavers/<db>weaver && make test`. Green means the manifest matches the
   spec, the weaver is reachable, fingerprints are real, and the golden examples
   pass.

## Boundaries (do not cross these)

- **Never weaken or delete the conformance / contract tests** (`WeaverConformanceTests`,
  the `weaverkit` suite, `braidworks.testing.contract`). They are the contract. If
  one fails, fix the code, not the test. Changing a check requires a deliberate,
  reviewed edit with justification — not a quiet edit to make CI pass.
- **`consumes` must be a registered shared key.** Don't invent a private input
  type — that makes an unreachable "island" weaver. Adding a genuinely new bridge
  key is a deliberate edit to `weaverkit/src/weaverkit/keys.py` *in the same PR*,
  with a one-line description of what produces it.
- **Never return `"unknown"` (or empty) from a fingerprint.** It silently disables
  cache invalidation. Use a release tag, dump date, or checksum.
- **Don't hand-edit generated `vocab.py`.** It mirrors the spec. Change the spec
  and regenerate; `verify` checks the two stay in sync.
- **`source_sample` in the spec must be real** — paste an actual snippet of the
  source data. It is the anti-hallucination guard: it proves the schema you mapped
  was observed, not invented.
- **Failures are values, not exceptions.** Return `WeaveStatus.NO_MATCH` / `ERROR`,
  not raised exceptions, except for structural problems (`BackendConfigurationError`,
  `UnsupportedCapability`, `BackendUnavailable`).
- **Keep `braidworks-core` domain-neutral.** No taxonomy/protein/etc. assumptions
  leak into core; weaver-specific types stay in the weaver package.
- **Never commit data artifacts.** Databases, dumps, and archives are multi-GB and
  git-ignored (`*.sqlite`, `*.tar.gz`, `/data/`). See `docs/database.md`.

## Conventions

- Python 3.12+, line length 100, ruff for lint + format.
- Every dataclass on a public boundary round-trips through `to_json()` / `from_json()`.
- Tests are per-package and cwd-sensitive (suites import `from tests....`); use the
  Makefile targets, which `cd` into the right place.

## Where to read more

- `weaverkit/docs/PITFALLS.md` — the short do/don't list of mistakes that recur.
- `weaverkit/docs/implementing-backends.md` — the per-`# TODO` contract for a
  backend's `fetch` / `fingerprint` / `is_configured` (the generated stubs link to it).
- `docs/weaver-implementation-guide.md` — the full build manual, per-module.
- `docs/weaver-roadmap.md` — which weavers to build next + the reachability model.
- `docs/architecture.md` — core abstractions and rationale.
- `weaverkit/README.md` — the spec/scaffold/conformance toolkit and design decisions.
