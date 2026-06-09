# Weaver implementation guide (for agents)

This is a build manual for an AI agent (or human) implementing a new Braidworks
weaver. It is prescriptive: follow the steps in order, change only what's marked,
and run the verification commands at each gate. When in doubt, **read the
corresponding file in `weavers/taxon_weaver/src/weavers/taxon_weaver/` — it is the source of truth,
this guide just orients you.**

> **Don't start by copying files by hand.** The deterministic path is
> `make new-weaver SPEC=… DEST=…`, which stamps the whole package from a
> `weaver.spec.toml` (see [weaverkit](../weaverkit/README.md)). This guide explains
> what the generated files *are* and what you must fill in; §2 covers the loop.
> The boundaries you must respect are in [AGENTS.md](../AGENTS.md).

- *Boundaries & the Spec→Scaffold→Implement→Verify loop* → [AGENTS.md](../AGENTS.md)
- *What to build next & why* → [weaver-roadmap.md](weaver-roadmap.md)
- *Mechanical recipe (short)* → [CONTRIBUTING.md](../CONTRIBUTING.md) §"Adding a new weaver"
- *Core abstractions & rationale* → [architecture.md](architecture.md)
- *The guardrail toolkit (spec/scaffold/conformance)* → [weaverkit/README.md](../weaverkit/README.md)
- *Local DB auto-setup design* → [local-db-setup-plan.md](local-db-setup-plan.md)
- *This guide* → the long version: what each generated file is + checklists.

---

## 0. Orient: the five things a weaver is

> **Shared runtime (read first):** the *records*, *mapper*, *dispatch*, and *backend
> ABC* now live in `braidworks-core` (`LookupRecord`/`ResolverRecord`, `map_lookup`/
> `map_resolver`, `BackendDispatchWeaver`, `BackendBase`). A scaffolded weaver
> **imports** them — it does not generate `intermediate.py` / `mapper.py` /
> `dispatch.py` / `backends/base.py`. The numbered concepts below still describe what
> each piece *does* (and match `taxon_weaver`, which keeps its own hand-tuned versions
> as the "bring your own plumbing" reference) — but for a new weaver, items 2 and 4
> are just `from braidworks.core import ...`.

1. A **`vocab.py`** — the strand `type_id`s, `Capability`s, and `WeaverManifest` (generated).
2. A **neutral record** every backend fills — `LookupRecord` / `ResolverRecord` (from core).
3. One or more **backends** (`backends/*.py`) — one per data source (local DB, REST API). *You write these.*
4. One **mapper** (`record → WeaveResult`, the single source of strand shape) — `map_lookup` / `map_resolver` (from core).
5. **Assembly + factory glue** — a `BackendDispatchWeaver` subclass (sets `MAPPER` + `MANIFEST`), a zero-config `build_<package>()` introspection builder (verify's target) + a configured builder (the two-builder convention), and a `WeaverProvider`.

Plus, around it: a **per-weaver `Makefile`**, **tests** (unit + contract mixins + opt-in live E2E), and — if the source ships a bulk file — a **`setup.py`** with `ensure_<db>_db(...)`.

The braider connects weavers automatically: **a weaver is reachable iff some
registered weaver produces a `type_id` it consumes.** So the single most important
design choice is making `consumes` use the **shared key types** from
[weaver-roadmap.md §1](weaver-roadmap.md) (`ncbi.taxon.id`,
`organism.scientific_name` + `ncbi.taxon.lineage`, `protein.uniprot.accession`, …),
never raw user input.

---

## 1. Decide before coding (write these down)

| Decision | Question | Example (madin_weaver) |
|---|---|---|
| DB name | What's the source? Name the package `<db>_weaver`. | `madin_weaver` (bacteria-archaea-traits) |
| Consumes | Which **shared key** identifies a record? | `ncbi.taxon.id` |
| Produces | Which `type_id`s + how do they group? | `microbe.trait.*` in `traits.core` / `traits.growth` |
| Backends | Bulk file → `local`; REST → `api`; both? | `local` (CC BY bulk CSV) |
| Identity/fingerprint | What versions the data? (never `"unknown"`) | dataset release tag / file checksum |
| License | Attribution / redistribution constraints? | CC BY — record in README |
| Terminal vs intermediate | Does it also emit cross-ref IDs others consume? | terminal (traits only) |

If `consumes` is not already produced by a registered weaver, you also need (or
must rely on) an upstream weaver — usually `taxon_weaver`.

---

## 2. Scaffold the package

Write the decisions above into a `weaver.spec.toml`, then generate the package:

```bash
make verify-weaver SPEC=path/to/weaver.spec.toml          # validate the spec first
make new-weaver    SPEC=path/to/weaver.spec.toml DEST=weavers/<db>_weaver
```

`weaverkit new` stamps the layout below, generating `vocab.py` so the manifest
already matches the spec (conformance passes by construction) and wiring up the
conformance test. The root `pyproject.toml` globs `members = ["weavers/*"]`, so the
new package is picked up by `make sync` automatically — no manual `members` edit.
(Keep the spec **outside** `weavers/` until you scaffold: the glob makes `uv` treat
any dir there as a member, so a spec-only `weavers/<db>_weaver/` breaks `uv run`.)
The only files you edit are the `# TODO` spots in the backend
stubs (§4/§6). The generated structure (see the repo-org proposal in
weaver-roadmap.md §5 — if `weavers/*` has landed, create under `weavers/`):

```
<db>_weaver/
  pyproject.toml
  Makefile
  src/<db>_weaver/
    __init__.py        # re-export build_<db>_weaver, vocab, the weaver class
    vocab.py
    intermediate.py
    mapper.py
    weaver.py
    dispatch.py        # copy taxon_weaver's; adapt the "needs" logic (see §6)
    factory.py
    provider.py
    setup.py           # only if there's a local bulk DB
    backends/
      __init__.py
      base.py          # copy; retype the abstract resolve() to your intermediate
      local.py         # if applicable
      api.py           # if applicable
  tests/
    conftest.py
    test_<db>_local.py / _api.py
    test_e2e_live.py
```

**`pyproject.toml`** (copy `weavers/taxon_weaver/pyproject.toml`, change name/packages/deps):

```toml
[project]
name = "<db>_weaver"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["braidworks-core", "httpx>=0.27"]   # local-DB plumbing (+platformdirs) comes via braidworks-core
[project.optional-dependencies]
test = ["pytest>=8.0", "pytest-asyncio>=0.23"]
[project.scripts]
<db>-weaver = "<db>_tools.cli:main"                  # only if you add a CLI
[tool.uv.sources]
braidworks-core = { workspace = true }
[tool.hatch.build.targets.wheel]
packages = ["src/<db>_weaver"]
[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
testpaths = ["tests"]
```

The **root** `pyproject.toml` `[tool.uv.workspace] members` already globs
`weavers/*`, so just run `uv sync --all-extras` (or `make sync`) and confirm it
imports — no manual member entry needed.

---

## 3. `vocab.py` — type IDs, capabilities, manifest

Pattern: define `type_id` constants, group them, build one `Capability` per
operation, and a `build_manifest(*, backends)` that takes the wired backends.
Reference: `weavers/taxon_weaver/src/weavers/taxon_weaver/vocab.py`.

```python
from braidworks.core import Capability, OutputGroup, WeaverManifest

# consumes a SHARED key (see weaver-roadmap §1) — do not invent a private input
TAXON_ID = "ncbi.taxon.id"

OXYGEN = "microbe.trait.oxygen"
METABOLISM = "microbe.trait.metabolism"
TEMP_OPTIMUM = "microbe.trait.temperature_optimum"

CORE_OUTPUTS = frozenset({OXYGEN, METABOLISM})
GROWTH_OUTPUTS = frozenset({TEMP_OPTIMUM})

WEAVER_ID = "madin"
WEAVER_VERSION = "1.0.0"
RESOLVE_TRAITS = "madin.resolve_traits"
MAX_BATCH_SIZE = None  # local DB handles any size; set the API page limit otherwise

def resolve_traits_capability(*, backends: tuple[str, ...]) -> Capability:
    return Capability(
        id=RESOLVE_TRAITS,
        consumes=frozenset({TAXON_ID}),
        produces=CORE_OUTPUTS | GROWTH_OUTPUTS,
        output_groups=(
            OutputGroup(id="core", outputs=CORE_OUTPUTS),
            OutputGroup(id="growth", outputs=GROWTH_OUTPUTS),
        ),
        backends=backends,
        max_batch_size=MAX_BATCH_SIZE,
    )

def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:
    return WeaverManifest(
        weaver_id=WEAVER_ID, version=WEAVER_VERSION,
        capabilities=(resolve_traits_capability(backends=backends),),
    )
```

**Rules:**
- **Output groups** are how partial computation caches. Requesting any output in a
  group triggers the whole group (`Capability.triggered_groups`); the mapper emits
  only `Capability.outputs_to_compute(requested)`. Group outputs that are computed
  by the same underlying operation.
- `consumes` is a **single type for the MVP** — the copied `dispatch.py` does
  `(input_type,) = tuple(cap.consumes)`. Multi-input needs more work; don't unless required.
- Add a one-line row to the interface table in [weaver-roadmap.md §1](weaver-roadmap.md).

---

## 4. `intermediate.py` — the neutral dataclass

One dataclass your backends fill and the mapper reads. It is **backend-neutral**
and must never be imported by `braidworks-core`. Include a status enum mirroring
`WeaveStatus` outcomes (resolved / ambiguous / no_match / error) and a `score`
for confidence. Reference: `weavers/taxon_weaver/src/weavers/taxon_weaver/intermediate.py`.

```python
from dataclasses import dataclass, field
from enum import Enum

class TraitMatchStatus(Enum):
    RESOLVED = "resolved"; AMBIGUOUS = "ambiguous"; NO_MATCH = "no_match"; ERROR = "error"

@dataclass
class TraitMatch:
    query: object
    status: TraitMatchStatus
    values: dict = field(default_factory=dict)   # {type_id: value}
    score: float | None = None
    requires_review: bool = False
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
```

---

## 5. `backends/` — one per data source

Copy `backends/base.py` and retype `resolve()` to return your intermediate. The
backend implements core's `BackendStrategy` (`name`, `is_configured()`,
`fingerprint()`) plus the one domain `resolve()`.

```python
class TraitBackend(ABC):
    name: str
    @abstractmethod
    def is_configured(self) -> bool: ...
    @abstractmethod
    def fingerprint(self) -> str: ...          # NEVER "unknown" — it keys the cache
    @abstractmethod
    async def resolve(self, capability_id, queries, *, groups: frozenset[str]) -> list[TraitMatch]:
        """One TraitMatch per input, in input order."""
```

**`local.py`** (bulk → SQLite). Mirror `backends/local.py`: **construct cheap and
never raise for a missing DB** — set `self._configured = db_is_valid(path)` and have
`is_configured()` return it (the dispatch gates on it; the actionable "build it"
error lives in the configured builder / `ensure_*` path, not `__init__`). One
connection per thread via `threading.local`, run sync queries off the loop with
`asyncio.to_thread`, derive `fingerprint()` from a stored dataset version (only ever
called when configured).

**`api.py`** (REST). Mirror `backends/datasets_v2.py`: an **injectable**
`httpx.AsyncClient` (tests pass an `httpx.MockTransport`), `api_key`/registration
where required, batched + paged requests, `logging.getLogger("<db>_weaver.api")`
INFO line on network use, a fixed `fingerprint()` like `"<db>-live"`.

**Fingerprint rule (critical):** versioned dataset → version string
(`"madin-2020-r1"`); live service → explicit `"<db>-live"`. Returning `"unknown"`
silently disables cache invalidation.

---

## 6. `dispatch.py` + `weaver.py` — assembly

Copy `dispatch.py`. It: looks up the capability, selects the backend (raising
`BackendUnavailable` if absent/unconfigured), extracts the single consumed value
per input, calls `backend.resolve(...)`, and runs the mapper. **Adapt the
"what does the backend need" line:** taxon_weaver computes
`need_lineage = "lineage" in cap.triggered_groups(requested_outputs)`. Generalize to
pass the triggered optional groups:

```python
groups = cap.triggered_groups(requested_outputs)
matches = await strategy.resolve(capability_id, queries, groups=groups)
```

`weaver.py` is tiny — subclass the dispatch weaver and set `MANIFEST` from the
wired backends (copy `weavers/taxon_weaver/src/weavers/taxon_weaver/weaver.py`):

```python
class MadinWeaver(BackendDispatchWeaver):
    def __init__(self, backends):
        if not backends: raise ValueError("MadinWeaver requires at least one backend")
        super().__init__(backends)
        self.MANIFEST = vocab.build_manifest(backends=tuple(sorted(backends)))
```

> `BackendDispatchWeaver` currently lives in the taxon package. Copy it for now;
> it will be promoted to a shared `weaverkit` once a second weaver confirms the
> abstraction. Keep your copy minimal-diff so that promotion is clean.

---

## 7. `mapper.py` — the single strand-shape source

The mapper is the contract: **all backends route through it, so all backends emit
identical strands.** Reference: `weavers/taxon_weaver/src/weavers/taxon_weaver/mapper.py`.

```python
def map_trait_match(match, *, capability, requested_outputs, backend, weaver_version) -> WeaveResult:
    triggered = capability.triggered_groups(requested_outputs)
    computed_groups = frozenset(triggered | {"core"})          # if core is always computed
    allowed = capability.outputs_to_compute(requested_outputs) # emit EXACTLY these
    status = _STATUS[match.status]                              # intermediate status -> WeaveStatus
    conf = confidence_from_score(match.score)
    provenance = (f"{vocab.WEAVER_ID}:{backend}",)
    strands = [
        Strand(t, v, confidence=conf, provenance=provenance)
        for t, v in match.values.items() if t in allowed and v is not None
    ]
    return WeaveResult(
        capability_id=capability.id, weaver_version=weaver_version, backend_used=backend,
        computed_groups=computed_groups, status=status, strands=tuple(strands),
        warnings=tuple(match.warnings), requires_review=match.requires_review,
    )
```

**Rules:**
- Emit only `outputs_to_compute(requested)`; report everything computed in
  `computed_groups` (lets the cache satisfy a later subset request).
- **Failures are values:** map "not found" → `WeaveStatus.NO_MATCH` (empty strands),
  multiple candidates → `WeaveStatus.AMBIGUOUS` (+ `candidates`, `requires_review=True`),
  per-record backend failure → `WeaveStatus.ERROR` (+ `errors`). Only *structural*
  problems raise (`BackendConfigurationError`, `BackendUnavailable`).
- Low confidence / fuzzy / ambiguous → set `requires_review=True` so it lands in the
  executor's `review_queue` rather than asserting silently.

---

## 8. `factory.py` + `provider.py` — the two-layer factory

`build_<db>_weaver(...)` (Layer 2) is the only place that knows how to construct
your backends. The `WeaverProvider` (Layer 1) is a thin wrapper for
`WeaverFactory`. Reference: `factory.py` + `provider.py`.

```python
def build_madin_weaver(*, db_path=None, auto_setup=False, refresh=False, enable_api=False, ...):
    backends = {}
    want_local = db_path is not None or auto_setup
    if want_local:
        resolved = _ensure_local_db(db_path, auto_setup=auto_setup, refresh=refresh)  # see §9
        backends["local"] = MadinLocalBackend(resolved)
    if enable_api:
        backends["api"] = MadinApiBackend(...)
    if not backends:
        raise BackendConfigurationError("configure at least one backend")
    return MadinWeaver(backends)

class MadinWeaverProvider:
    weaver_id = vocab.WEAVER_ID
    def build(self, config): return build_madin_weaver(**dict(config))
```

If you have a local DB, copy taxon_weaver's `factory._ensure_local_db` +
`_interactive` + `_prompt_for_setup` (interactive prompt vs actionable error vs
consent). Otherwise omit.

---

## 9. `setup.py` — local DB acquisition (only if bulk file)

If the source ships a bulk file, the generic acquisition plumbing — default-path
resolution (`BRAIDWORKS_DATA_DIR` / platformdirs cache), consent gate (`auto=` /
`BRAIDWORKS_AUTO_DOWNLOAD`), download, checksum verify, disk precheck, cross-process
lock, atomic temp→`os.replace`, idempotent reuse — lives in
**`braidworks.core.localdb.ensure_local_db`**. Your `setup.py` supplies only the
domain pieces: `db_is_valid(path)`, `_build(target)` (download + parse into the DB,
recording the source version), and the consent message; then delegate to
`ensure_local_db`. The `[bulk]` spec table makes the scaffold stamp this shape plus
a `<db>-ensure` CLI for you. `weavers/taxon_weaver/src/weavers/taxon_weaver/setup.py` is the worked
example (it adds `check_for_update` on top).

**Reuse shortcut:** if the source is already in **NCBI taxdump format** (e.g.
GTDB via gtdb-taxdump), call `taxonomy_resolver.build.build_taxonomy_database`
directly instead of writing a parser.

Design rationale and the full decision log are in
[local-db-setup-plan.md](local-db-setup-plan.md).

---

## 10. Tests — three layers

1. **Unit / behavior** (per backend): exact match, no-match, ambiguous, group
   selection (core-only vs +optional), batch order/length. Local: build a tiny
   synthetic DB in a fixture (see `weavers/taxon_weaver/tests/conftest.py`). API: drive an
   `httpx.MockTransport` (see `tests/test_taxon_weaver_api.py`).
2. **Contract mixins** (per backend): subclass `WeaverOrderContractTests` and
   `CacheFingerprintTests` from `braidworks.testing.contract`. Provide ≥5 distinct
   samples. See `tests/test_taxon_weaver_local.py`.
3. **Opt-in live E2E**: gate with
   `pytest.mark.skipif(not os.environ.get("BRAIDWORKS_RUN_LIVE"), …)`; ensure the
   real DB, run a large/real batch, assert exact resolution + known-truth rows.
   Copy `tests/test_e2e_live.py`. It must **self-skip** without the env var.

`conftest.py` note: taxon_weaver tests import `from tests....`; that only resolves
with `pythonpath = ["."]` + running from the package dir — keep both.

---

## 11. `Makefile` — weaver-specific macros

Copy `weavers/taxon_weaver/Makefile`: `test`, `test-live` (the `BRAIDWORKS_RUN_LIVE` E2E),
`ensure` (if there's a local DB), `lint`, `fmt`, `help`. Then make the **root**
`test-weaver` (or a per-weaver target) delegate: `$(MAKE) -C <path> test`. Add the
package's `src`/`tests` to the root `LINT_PATHS`.

---

## 12. Verify (run at each gate, and before declaring done)

```bash
uv sync --all-extras
make -C <db>_weaver test       # unit + contract mixins; live E2E self-skips
make lint                     # ruff over all packages (add your paths to LINT_PATHS)
# once, to prove the real path:
make -C <db>_weaver test-live  # BRAIDWORKS_RUN_LIVE=1 — real download/build/resolve
```

Then plan an end-to-end chain to confirm reachability, e.g.:
`organism.name → [taxon_weaver] → ncbi.taxon.id → [<db>_weaver] → microbe.trait.*`.

---

## 13. The checklist (done = all checked)

- [ ] DB-named package under `weavers/` (auto-included by the `weavers/*` glob); own `Makefile`; `uv sync` clean.
- [ ] `vocab.py`: type_ids + capabilities + output groups; **`consumes` a shared key**
      (roadmap §1), not raw input; interface-table row added to weaver-roadmap.md.
- [ ] Neutral intermediate; never imported by `braidworks-core`.
- [ ] Backend(s) implement `name`/`is_configured`/`fingerprint`/`resolve`;
      `fingerprint` is version-specific, never `"unknown"`.
- [ ] One mapper = single strand-shape source across all backends.
- [ ] `execute_batch` returns one result per input, in input order.
- [ ] Failures are values (`NO_MATCH`/`AMBIGUOUS`/`ERROR`); low confidence →
      `requires_review`; only structural problems raise.
- [ ] Dataclasses on the public boundary round-trip `to_json`/`from_json`.
- [ ] `build_<db>_weaver` + `WeaverProvider`; at least one backend required.
- [ ] Local DB (if any): `ensure_<db>_db` + `<db>-weaver ensure`; default path is
      DB-named; DB artifacts git-ignored (never commit multi-GB data).
- [ ] Tests: unit + contract mixins per backend + opt-in live E2E that self-skips.
- [ ] `make -C <path> test` and `make lint` green; live E2E passes once.
- [ ] License/attribution recorded in the weaver README.

---

## 14. Common pitfalls

- **Consuming raw input instead of a shared key** → the weaver is an island; the
  braider can't chain it. Consume `ncbi.taxon.id` / `…lineage` / `uniprot.accession`.
- **`fingerprint()` returning `"unknown"` or a constant for versioned data** →
  stale cache hits across data updates.
- **Mapper emitting more than `outputs_to_compute`** → leaks ungrouped outputs and
  corrupts cache group accounting.
- **Raising on "not found"** → breaks the result-bucket contract; return `NO_MATCH`.
- **Committing the DB** → it's multi-GB and git-ignored; ship `ensure_*` instead.
- **Forgetting `pythonpath=["."]`** → `from tests....` imports fail under pytest.
- **Not adding paths to root `LINT_PATHS`** → CI lint silently skips your package.

---

## 15. Reference index

| Need | Read |
|---|---|
| What/why to build next | [weaver-roadmap.md](weaver-roadmap.md) |
| Short mechanical recipe | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| Core abstractions, two-layer factory | [architecture.md](architecture.md) |
| Local DB auto-setup decisions | [local-db-setup-plan.md](local-db-setup-plan.md) |
| Building the NCBI DB | [database.md](database.md) |
| Reference implementation | `weavers/taxon_weaver/src/weavers/taxon_weaver/` (every file maps to a §above) |
| Core types | `braidworks-core/src/braidworks/core/` — `capability.py`, `weaver.py`, `result.py`, `strand.py` |
| Shipped test mixins | `braidworks-core/src/braidworks/testing/contract.py` |
