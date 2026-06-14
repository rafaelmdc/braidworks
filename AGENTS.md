# AGENTS.md — working in Braidworks

Instructions for an AI agent (or human) contributing to this repository. Read this
before making changes. It is intentionally short and prescriptive; the deeper
"why" lives in `docs/`.

## What this repo is

Braidworks is a `uv` workspace of composable biological data resolvers called
**weavers**. `braidworks-core` is the domain-neutral framework; each weaver (e.g.
`taxon_weaver`) wraps one data source. `weaverkit` is the toolkit that makes adding
a weaver deterministic rather than improvised.

## Commands

```bash
make sync                 # set up the venv (uv sync --all-extras)
make test                 # run every package's suite (core + weavers + weaverkit)
make lint                 # ruff check across all packages
make fmt                  # ruff format

# adding a weaver (weavers live under weavers/, e.g. weavers/taxon_weaver/, weavers/example_weaver/):
make new-weaver  SPEC=path/to/weaver.spec.toml DEST=weavers/<db>_weaver
make verify-weaver SPEC=path/to/weaver.spec.toml PACKAGE=<db>_weaver
make index                # rebuild docs/weavers-index.tsv (machine) + docs/keys-index.md (human)
```

CI runs `make lint` and `make test`; both must stay green.

## Adding a weaver: the Spec → Scaffold → Implement → Verify loop

Do **not** hand-write a weaver from scratch. Follow the loop:

1. **Spec.** Write a `weaver.spec.toml` (see `weaverkit/tests/fixtures/` for complete
   examples, and the field reference in `weaverkit/README.md`). Pick `consumes` from
   the **shared-key registry** (`weaverkit/src/weaverkit/keys.py`)
   so the weaver is reachable, and set `kind` (`lookup` for clean ID→data, the
   default; `resolver` for fuzzy/ambiguous name matching — it generates the richer
   candidate/`MatchStatus` shape). Validate it: `make verify-weaver SPEC=... ` —
   it reports every problem at once.
2. **Scaffold.** `make new-weaver SPEC=... DEST=weavers/<db>_weaver` (under `weavers/`,
   so the generated `IMPLEMENTATION.md`'s `../../weaverkit/...` links resolve). This stamps a
   complete, importable package whose manifest already matches the spec and whose
   conformance test is wired up. It also generates two per-weaver docs:
   `IMPLEMENTATION.md` (the one-time worklist to finish the stubs) and
   `CONTRIBUTING.md` (how to *extend* the weaver later — add a trait/capability/backend;
   fill in its "Expansion notes" with weaver-specific limitations as you build). The
   root `pyproject.toml` already globs `members = ["weavers/*"]`, so a scaffolded
   weaver is picked up by `make sync` with no manual edit.
   > **Keep the spec outside `weavers/` until you scaffold.** The `weavers/*` glob
   > makes `uv` treat *any* directory there as a workspace member, so a half-created
   > `weavers/<db>_weaver/` holding only the spec makes every `uv run …` fail with
   > "missing a pyproject.toml". Put the spec in a scratch path (e.g. `/tmp` or repo
   > root), run `new-weaver`, and the scaffold writes the spec copy into the package.
3. **Implement.** The only edits you should need are the spots marked `# TODO`:
   each backend's `fetch` (currently `NotImplementedError`) and its `fingerprint`
   (currently a placeholder). Normalize each source result into the generated
   core `LookupRecord` / `ResolverRecord`; the shared core mapper turns it into
   strands. Add real
   golden examples to the spec. For real-world use add a *configured* builder
   alongside the generated zero-config `build_<package>()` (two-builder convention —
   the generated `factory.py` has a commented skeleton); if no backend reads
   bundled data, add a `build_<package>_fixture()` so `verify --strict` can run
   golden against a tiny deterministic dataset.
   > For HTTP backends, follow the **Fetch patterns** in
   > `weaverkit/docs/implementing-backends.md`: classify 400/404 as `NO_MATCH` with
   > `braidworks.core.is_not_found_status` (5xx/network → error), make ambiguous picks
   > deterministic (sort + id tiebreak), and dedup→sort→cap "list" outputs while
   > reporting the true total. Fill in `tests/test_e2e_live.py` (not the placeholder).
4. **Verify.** `make verify-weaver SPEC=... PACKAGE=<db>_weaver` (spec valid +
   manifest matches + reachable + real fingerprints) and `cd weavers/<db>_weaver &&
   make test`. The **definition of done** is the `--strict` gate (what the generated
   `IMPLEMENTATION.md` ends on): `weaverkit verify --spec ... --package <db>_weaver
   --strict` — it additionally fails while any `# TODO` placeholder remains and runs
   the golden examples (against a fixture or a configured backend; plain `verify`
   lets them skip).

## Boundaries (do not cross these)

- **Never weaken or delete the conformance / contract tests** (`WeaverConformanceTests`,
  the `weaverkit` suite, `braidworks.testing.contract`). They are the contract. If
  one fails, fix the code, not the test. Changing a check requires a deliberate,
  reviewed edit with justification — not a quiet edit to make CI pass.
- **`consumes` must be a registered shared key.** Don't invent a private input
  type. Adding a genuinely new bridge key is a deliberate edit to
  `weaverkit/src/weaverkit/keys.py` *in the same PR*, with a one-line description of
  what produces it. (A registered key keeps the weaver *connectable*; whether a
  producer exists *yet* is a softer matter — see "Connectivity" below.)
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

## Connectivity: aim to connect, islands are allowed

Weavers are worth most when they *link* — when another weaver produces a key this
one consumes, so data flows across them. So **always try to connect**: prefer
`consumes` keys that something already produces. Run `make index` and read
`docs/weavers-index.tsv` (the `unmet_inputs` column) to see what's already in play
before picking inputs. For a human-readable, key-by-key view of who produces and
consumes each key, read `docs/keys-index.md` (generated by the same `make index`).

But a new weaver **might not be able to connect**, and **that is fine**. If a source's
only sensible input isn't produced by anything yet, keep the weaver anyway — it still
retrieves real information when called directly, and a later weaver may produce the key
and link it in. An unmet input is a hint, not a failure: `verify` does not reject it.

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
