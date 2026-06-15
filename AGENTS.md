# AGENTS.md — working in Braidworks

Instructions for an AI agent (or human) contributing to this repository. Read this
before making changes. It is intentionally short and prescriptive; the deeper
"why" lives in `docs/`.

## What this repo is

Braidworks is a `uv` workspace of composable biological data resolvers called
**weavers**. `braidworks-core` is the domain-neutral framework; each weaver (e.g.
`ncbi_weaver`) wraps one data source. `weaverkit` is the toolkit that makes adding
a weaver deterministic rather than improvised.

## Commands

```bash
make sync                 # set up the venv (uv sync --all-extras)
make test                 # run every package's suite (core + weavers + weaverkit)
make lint                 # ruff check across all packages
make fmt                  # ruff format

# adding a weaver (weavers live under weavers/, e.g. weavers/ncbi_weaver/, weavers/example_weaver/):
make new-weaver  SPEC=path/to/weaver.spec.toml DEST=weavers/<db>_weaver
make verify-weaver SPEC=path/to/weaver.spec.toml PACKAGE=<db>_weaver
make index                # rebuild docs/weavers-index.tsv (machine) + docs/keys-index.md (human)
make view                 # regenerate the offline HTML network view -> docs/braidworks-network.html
make serve                # interactive GUI to build/run braids in the browser (needs the [serve] extra)

uv run weaverkit references          # print the source citations for all discovered weavers
make tags-check                      # list any package versions missing a release tag
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
   > **Provenance metadata (drives automatic references — issue #1).** Fill the
   > `[weaver]` fields: `title` (one-line description, shown in the network-view card),
   > `source_url`, `license` (a **known identifier** — `CC-BY-4.0`, `CC0-1.0`,
   > `Public Domain`, `Open` … see `braidworks.core.licenses.LICENSE_RULES`), `citation`
   > (DOI/reference), `attribution` (provider to credit). These flow into the runtime
   > `WeaverManifest` and are emitted as citations on braid results / `weaverkit
   > references` / the visualizer. `verify` *warns* if the license is unknown (treated
   > as `restricted`) or an attribution-required license has no citation — fix those.
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
   > **Run the live E2E after touching any `api` backend.** CI only exercises mocked
   > `httpx.MockTransport` responses, so upstream schema drift silently turns a live
   > backend into all-`NO_MATCH` while unit tests stay green. Fill in
   > `tests/test_e2e_live.py` with a real known-truth example (`--strict` now flags the
   > scaffold's `"TODO-real-input"` placeholder) and run
   > `BRAIDWORKS_RUN_LIVE=1 make -C weavers/<db>_weaver test-live` (real network). When a
   > backend misbehaves, `curl` the endpoint and diff its shape against your mock first.

## Capability naming: resolve / list / describe

Name every capability by the **shape of its lookup**, so callers can predict its
output from the verb (the network view and `keys-index` group by it):

- **`resolve_<thing>`** — fuzzy/ambiguous input → an identifier. The `resolver` kind:
  emits `candidates` + a `MatchStatus`; may need review. (e.g. messy name → accession.)
- **`list_<things>`** — one identifier → a **set** of related identifiers/records
  (e.g. a protein → all its PDB ids / GO terms / pathways). Plural.
- **`describe_<thing>`** — one identifier → **that one entity's** attributes
  (e.g. one PDB id → its title/method/date). Singular.
- **`map_to_<x>` / `map_from_<x>`** — deterministic identifier ↔ identifier
  cross-reference (no fuzziness, no attributes). Use when a single source maps many
  id types to/from a hub key (e.g. UniProt ID-mapping). See `consumes_any` below.

A `list_*` and its matching `describe_*` form a pair: `list_*` produces a set key,
`describe_*` *consumes* that same key — so a fanned member is drillable.

## Cardinality & fan-out (`set_outputs`)

A capability that produces a **set** identifier (many values for one input) declares
it in the spec's `set_outputs` (a subset of `produces`). At runtime the executor can
**fan out** along that key — fork one input into an independent child per member and
continue the braid per child — under an `ExpandPolicy` (`TOP` default keeps the best
one; `TOP_K`/`ALL` expand). Children carry `parent_id` back to the originating input.

When you add a `set_outputs` key:
- It must be a registered **shared key** (something can consume it), not a leaf —
  fan-out only matters if a `describe_*`/downstream weaver consumes it.
- Backends still **dedup → sort → cap** the display list and report the true total;
  the set key is the *full* distinct ordered set (the fan dimension), uncapped.
- Bump the weaver and raise its floor to `braidworks-core>=0.2.1` (where
  `Capability.set_outputs` landed). See `docs/fanout-roadmap.md`.

## Alternative inputs (`consumes_any`)

By default a capability's `consumes` is a **conjunction** — it needs *all* those types
together, and such multi-input capabilities are **not** routed by the planner's graph.
Set **`consumes_any = true`** to make `consumes` a set of **alternatives**: any one
present input suffices, and `build_graph` offers an edge from *each* alternative input to
each produced type. The backend dispatches on whichever input strand is present.

This lets **one** capability be the routable edge for many interchangeable inputs (e.g.
`{gene id, ensembl id, pdb id, …} → accession`) instead of one near-identical capability
per source. It's the input-side mirror of routing by **requested output** (one capability,
one `consumes`, many `produces` — the backend keys off `requested_outputs`). A hub source
is naturally **two directional capabilities** (`map_to_<hub>` with `consumes_any`,
`map_from_<hub>` routing by output) — not 20 edges, not one opaque param-tool. See
`weaverkit/docs/decisions.md` (H) and `uniprot_weaver`'s `map_to_accession` /
`map_from_accession`. Needs `braidworks-core>=0.8.0`.

## Per-query parameters (`[[capability.parameter]]`)

A capability's four knobs are: `consumes`/`produces` (the **join**), output groups
(**which** fields), `backends` (**where**), and **parameters** (**how** — filters,
sort, page size, thresholds). Parameters are the per-query options an API exposes that
aren't identifiers. Declare each in the spec:

```toml
[[capability.parameter]]
name = "assembly_level"
type = "string"            # string | int | float | bool
enum = ["complete", "chromosome", "contig"]   # optional; restricts values
default = "complete"        # optional; used when the caller omits it
description = "Assembly completeness filter"
```

- **Defaults preserve determinism**: omitting every parameter reproduces today's
  behaviour, and the *effective* params (defaults + caller overrides) fold into the
  cache key, so a default call shares cache entries and a parameterised call is a
  distinct entry. The planner never routes on parameters — they're refinements on a
  step, not bridges.
- A backend reads them from the `params` argument of `fetch` (validated + defaulted by
  the time it arrives). The CLI exposes them as `--param name=value`; `braidworks
  weavers` lists each capability's declared parameters.
- Use a parameter for a *knob* (filter/sort/threshold); use **output groups** for
  "which fields"; mint a **separate capability** only when it produces a different set
  of ids. Raise the weaver's core floor to `braidworks-core>=0.4.0` (where
  `Capability.parameters` landed).

## Versioning, tags & releasing

- **Each package versions independently** (`braidworks-core`, `weaverkit`, every
  `weavers/*`); dependents pin core with a **floor, no ceiling**
  (`braidworks-core>=X.Y.Z`). Keep backwards compatibility by default.
- **A weaver's version lives in THREE sites that must agree:** `weaver.spec.toml`
  `version`, `pyproject.toml` `version`, and `vocab.py` `WEAVER_VERSION` (the last is
  generated from the spec). `verify` *warns* on `spec` ≠ `pyproject` drift. When you
  change a weaver's manifest/behaviour, patch-bump all three. If a backend now needs a
  newer core API, raise its `braidworks-core>=` floor in the same change.
- **Do NOT create git tags by hand.** Tagging is automated:
  `.github/workflows/release-tags.yml` runs on every push to `main` and creates+pushes
  `<package>-v<version>` for any package whose current version isn't tagged yet. So:
  bump the version in your PR, merge, and the tag appears on its own. Locally,
  `make tags-check` lists missing tags; `make tags` creates them.

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
- **Don't hand-edit generated `vocab.py`.** It mirrors the spec (capabilities +
  `provenance` + `title`). Change the spec and regenerate (`weaverkit new --force`);
  `verify` checks the two stay in sync. **Exception:** `ncbi_weaver` is hand-written
  ("bring your own plumbing" reference) — its `vocab.py` has custom module-level
  constants, so regenerating it from the scaffold *clobbers* them; edit it by hand. The
  scaffold also generates the `[project.entry-points."braidworks.weavers"]` block, which
  makes the weaver discoverable (network view / `weaverkit references` / arq) — don't
  remove it.
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
consumes each key, read `docs/keys-index.md` (generated by the same `make index`), or
query the live registry with `braidworks keys` / `braidworks path --from … --to …`
(the `braidworks` query CLI ships with `braidworks-core`).

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
