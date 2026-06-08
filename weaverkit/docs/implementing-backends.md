# Implementing a weaver backend

This is the reference for the `# TODO` spots in a scaffolded weaver's
`src/<db>weaver/backends/<backend>.py`. The scaffold generates everything else;
you implement a backend by filling in three things — `is_configured`,
`fingerprint`, and `fetch` — plus adding golden examples to the spec.

Each generated `# TODO` links to the matching section below. Read only the section
you're working on; the [wiring overview](#how-it-all-wires-together) explains how
your backend fits the rest and is the same for every weaver. Skim
[PITFALLS.md](PITFALLS.md) first — the short list of mistakes that recur.

**Two worked references, by altitude:**

- **`exampleweaver/`** — the canonical *minimal* one: a `lookup` weaver,
  `ncbi.taxon.id → traits` from a ~5-row bundled CSV, ~80 lines you can read in a
  minute. It is literally `weaverkit new` + the three TODOs filled in, and it
  passes `weaverkit verify --strict`. **Copy this shape.** Start at
  `exampleweaver/src/exampleweaver/backends/local.py`.
- **`taxonweaver/`** — the *advanced, real-world* one you graduate to: a
  `resolver` (fuzzy matching, candidates), two backends (local SQLite + a live
  API), and a multi-GB bulk DB. Far more code; reach for it once the minimal
  pattern is clear.

---

## Builders: introspection vs configured vs fixture

The generated `factory.py` follows a two-builder convention (decisions.md C/D):

- **`build_<package>()`** — the **zero-config introspection** builder `weaverkit
  verify` calls. It wires every declared backend *present but possibly
  unconfigured*, never raises for missing data, and gives a manifest-complete
  weaver to inspect. The scaffold generates this for you.
- **a configured builder** (you write it, usually domain-named, e.g.
  `build_ncbi_weaver(...)`) — takes real config (db paths, API keys, injected
  clients) and may raise if nothing is usable. A commented skeleton sits at the
  bottom of the generated `factory.py`.
- **`build_<package>_fixture()`** (optional) — only if no backend reads bundled
  data; lets `verify --strict` run golden against a tiny deterministic dataset
  (see [golden under `--strict`](#golden-under---strict-provide-a-fixture-the-build_package_fixture-hook)).

`weaver_id` may differ from the package name (taxonweaver's is `ncbi`); verify
always targets `build_<package>()`.

## Connectivity: aim to connect, but an island is still allowed

A weaver is most useful when it *links* — when some other weaver produces a key it
consumes, so results can flow from one to the next. So always try to connect:
pick `consumes` keys from the shared-key registry (`weaverkit/src/weaverkit/keys.py`)
and, where you have a choice, prefer an input that another weaver already produces.
`weaverkit index` shows you which keys are in play (the `unmet_inputs` column flags
consumed keys nothing currently produces).

But sometimes a source simply can't connect — its only sensible input isn't produced
by anything else yet. **That is fine.** Keep the weaver: it can still retrieve real
information when called directly with that input, and a future weaver may produce the
key and link it in later. An unmet input is a hint, not an error — `verify` does not
fail on it. The one hard rule stays: the input must still be a *registered* shared key
(add the new bridge key to `keys.py` in the same PR), so the door to connecting is
open even if nothing walks through it today.

## How it all wires together

One capability call flows through fixed, generated machinery — your backend is the
only custom link:

```
StrandSet(s)
   │   (BackendDispatchWeaver.execute_batch — generated)
   │   pulls each consumed type_id off the StrandSet
   ▼
queries: list[{consumed_type_id: value}]        one dict per input entity
   │   (your backend — the only part you write)
   ▼
YourBackend.fetch(...) -> list[<Db>Record]      one record per input, in order
   │   (mapper.map_record — generated)
   │   keeps only requested outputs; sets status from found/error
   ▼
list[WeaveResult]                               one per input, in order
```

What this means for you:

- You never build `WeaveResult`/`Strand` objects or worry about output groups,
  requested-output filtering, or status codes — the **mapper** does that from your
  `<Db>Record`. Your job is only: *look it up, fill the record.*
- The **dispatch** guarantees `fetch` is only called with the backend selected and
  configured; an unconfigured backend raises `BackendUnavailable` upstream.
- The **manifest** (in `vocab.py`) is generated from `weaver.spec.toml`, so the
  capabilities, `consumes`, `produces`, and output groups already match the spec.
  Don't hand-edit `vocab.py` — change the spec and regenerate.

The neutral record you fill (`src/<db>weaver/intermediate.py`):

```python
@dataclass
class <Db>Record:
    query: dict[str, Any]         # the input you were given (echo it back)
    found: bool = False           # True on a hit
    values: dict[str, Any] = ...  # produced type_id -> value (hits only)
    error: str | None = None      # per-entity failure message (data problems != exceptions)
```

---

## lookup vs resolver weavers

The spec's `kind` field decides the shape of the generated `intermediate.py` and
`mapper.py` — pick it up front, it changes what `fetch` returns:

- **`kind = "lookup"`** (default) — clean ID→data. The input already identifies the
  record exactly (a taxid, an accession). The `<Db>Record` is flat:
  `found` / `values` / `error`. Most weavers are this.
- **`kind = "resolver"`** — fuzzy/ambiguous matching (names → ids, like
  `taxonweaver`). The record carries a `MatchStatus`
  (`RESOLVED` / `FUZZY_UNIQUE` / `AMBIGUOUS` / `NO_MATCH` / `ERROR`), an optional
  `score`, a `requires_review` flag, and a list of `Candidate`s for the ambiguous
  case. The generated mapper turns these into `OK` / `AMBIGUOUS` (with
  `candidates`) / `NO_MATCH` / `ERROR` and sets `requires_review`.

The `fetch` contract below is written for `lookup`; the resolver differences are
called out inline. Everything else (dispatch, manifest, registration, the cache
contract) is identical.

### Always-computed groups (`always_computed_groups`)

The mapper reports `computed_groups` — the output groups actually computed — as part
of the **cache key**. Normally that's just the groups whose outputs were requested.
But some backends compute a group *unconditionally*: a resolver, for instance,
always resolves the name → id (`core`) before it can fetch `lineage`, even when the
caller asked only for lineage. If that internal work isn't reported, the cache key
under-counts what was computed.

Declare it per capability in the spec — don't hand-edit the mapper:

```toml
[[capability]]
id = "resolve_name"
consumes = ["organism.name"]
always_computed_groups = ["core"]   # always computed, even if only lineage is asked
```

The generated `vocab.py` emits an `ALWAYS_COMPUTED_GROUPS` map and the mapper unions
it into `computed_groups`. (This only affects the reported `computed_groups`/cache
key — it does *not* emit the group's strands unless they were requested.)

---

## is_configured

`is_configured()` reports whether this backend can actually run *in this instance*
— the DB file exists and opened, or the API base URL / key is present. The
generated stub hardcodes `self._configured = False`; set it from a real check in
`__init__` (or lazily).

- While it returns `False`, the dispatch raises `BackendUnavailable` rather than
  calling `fetch`, and the conformance **golden tests skip** this backend (they
  need real data). That's why a freshly scaffolded weaver is green but inert.
- Keep it cheap and side-effect-free — it may be called just to decide routing.

```python
def __init__(self, db_path: Path | None = None) -> None:
    self._db_path = db_path or default_db_path()
    self._configured = self._db_path.exists()
```

---

## API keys

If a backend talks to a remote API that needs a key, you don't wire the key
plumbing by hand — declare it once in the spec and the scaffold generates it. Set
the weaver-level `api_key` field:

```toml
[weaver]
# ...
api_key = "required"   # "none" (default) | "optional" | "required"
```

- **`none`** (default) — no key. Every backend gets the plain stub.
- **`required`** — the API is unusable without a key.
- **`optional`** — the API works without a key, but one unlocks more (higher rate
  limits, private data).

When `api_key` is `optional` or `required`, every **non-`local`** backend (the
`local` backend reads a bundled/built file, so it never needs a key) is stamped
from the API variant instead of the plain stub. That variant:

- defines `API_KEY_ENV = "<DB_NAME>_API_KEY"` (e.g. `UNIPROT_API_KEY`) and reads
  the key in `__init__` with **explicit-arg-then-environment** precedence:

  ```python
  def __init__(self, api_key: str | None = None) -> None:
      self._api_key = api_key or os.environ.get(API_KEY_ENV)
  ```

- wires `is_configured()` to the declared need, so routing and the golden-test skip
  behave correctly out of the box:
  - `required` → `return self._api_key is not None` (unconfigured, and golden tests
    skip, until the env var is set);
  - `optional` → `return True` (the backend always runs; the key just improves it).

You implement only the call itself, in `fetch`: send `self._api_key` with each
request using whatever scheme the API expects, e.g.
`headers={"Authorization": f"Bearer {self._api_key}"}`. The key is already loaded;
don't re-read the environment in `fetch`.

`api_key` is also surfaced in `weaverkit index` (the `api_key` column), so the key
requirements of every weaver are visible at a glance.

---

## fingerprint

`fingerprint()` returns a **stable, version-specific** string identifying the data
this backend serves. It is part of the cache key, so the rule is two-sided:

- it must **change when the underlying data changes** (new dump, new release), and
- it must be **identical for identical data** (don't put a timestamp-of-now in it).

Never return `""` or `"unknown"` — that silently disables cache invalidation, and
`weaverkit.conformance.check_fingerprints` rejects it. The spec's
`fingerprint_source` field records *what* versions the data (a release tag, a dump
date, a checksum); derive the fingerprint from that.

```python
def fingerprint(self) -> str:
    # local bulk file: tie to the release recorded at build time
    return f"madin-local-{self._release_tag}"     # e.g. "madin-local-v1.2.0"

def fingerprint(self) -> str:
    # live API with no version surface: name the contract, not "live"-of-now
    return "uniprot-api-rest-v1"
```

If your local backend builds a DB from a dump, record the source version at build
time (e.g. in a metadata table) and read it here — mirror `taxonweaver`'s
`source_dump_md5` approach.

---

## fetch

`fetch` is the lookup. Contract:

```python
async def fetch(
    self,
    capability_id: str,
    queries: list[dict[str, Any]],
    *,
    requested_outputs: frozenset[str],
    groups_to_compute: frozenset[str],
) -> list[<Db>Record]:
```

Hard rules:

- **One record per input query, in the same order.** The dispatch aligns results
  to inputs positionally — never drop, reorder, de-duplicate, or merge. If a
  source API returns results keyed by id, re-expand to input order (see
  `BaseWeaver._reorder_by_key` in core for the pattern).
- **Hit:** `record.found = True` and `record.values = {produced_type_id: value, …}`.
  Only include keys this capability *produces* (see the spec); the mapper filters
  to the requested subset and ignores extras. Values must be JSON-serializable
  (str/int/float/bool/list/dict).
- **Miss:** `record.found = False`. A miss is a normal data outcome (`NO_MATCH`),
  **not** an error.
- **Per-entity failure:** `record.error = "<why>"`. Do **not** raise for data
  problems — failures are values. Reserve exceptions for structural faults
  (misconfiguration), which should surface from `is_configured`/construction.

Parameters you can use:

- `capability_id` — which capability is running, if this backend serves more than
  one. Branch on it when a backend answers several capabilities differently.
- `requested_outputs` — the externally requested type_ids. Optional optimization:
  skip computing expensive `values` nobody asked for. (Correctness doesn't depend
  on it — the mapper filters anyway — but it can save work.)
- `groups_to_compute` — the **resolved** set of triggered output-group ids (the
  dispatch computed it from `requested_outputs` via `Capability.triggered_groups`).
  Gate expensive paths on membership in it — `if "lineage" in groups_to_compute:` —
  instead of re-deriving group semantics from `requested_outputs` yourself. This is
  the dispatcher-owns-interpretation / backend-owns-fulfillment split (decisions.md B).

Example (local SQLite, single-input capability keyed on `ncbi.taxon.id`):

```python
async def fetch(self, capability_id, queries, *, requested_outputs, groups_to_compute):
    records: list[MadinRecord] = []
    for q in queries:
        taxid = q.get("ncbi.taxon.id")
        row = self._lookup(taxid)            # your DB access
        if row is None:
            records.append(MadinRecord(query=q, found=False))
            continue
        records.append(
            MadinRecord(
                query=q,
                found=True,
                values={
                    "microbe.trait.metabolism": row["metabolism"],
                    "microbe.trait.gram_stain": row["gram_stain"],
                    "microbe.trait.optimum_temp": row["optimum_tmp"],
                },
            )
        )
    return records
```

Multiple consumed keys: a `query` dict carries all of them, e.g.
`{"organism.scientific_name": "...", "ncbi.taxon.lineage": [...]}`. Use whichever
the source needs.

**Resolver variant** (`kind = "resolver"`): instead of `found`, set
`record.status` to a `MatchStatus` and, for the ambiguous case, populate
`record.candidates` with `Candidate(values=…, score=…)`; set `record.score` /
`record.requires_review` for fuzzy single matches. The generated `fetch` stub and
mapper already reflect this — see [lookup vs resolver](#lookup-vs-resolver-weavers).

---

## golden examples (in the spec, not the code)

Add known input→output pairs to `weaver.spec.toml` so conformance can prove the
backend actually returns the right data:

```toml
[[golden]]
capability = "resolve_traits"
input  = { "ncbi.taxon.id" = "562" }       # keys must be in the capability's consumes
expect = { "microbe.trait.gram_stain" = "negative" }   # keys must be in its produces
```

`WeaverConformanceTests.test_golden_examples` runs each one through `execute` on the
configured backend and checks every `expect` key comes back with the expected value.
They **skip** (in plain `verify`) while the backend is unconfigured, so add them
alongside `fetch`. Pick inputs whose answers are stable and you can verify.

### Golden under `--strict`: provide a fixture (the `build_<package>_fixture()` hook)

`verify --strict` (definition-of-done) must *run* golden, reproducibly, without
external data (see [decisions.md](decisions.md) Decision E). It picks the data to
run against in this order:

1. `build_<package>_fixture()` in your `factory.py`, if present — a builder that
   returns a weaver wired against a **tiny, deterministic dataset** (committed or
   synthesized at call time; no download, no network). This is the preferred path
   for any weaver whose real backend needs a large or external source.
2. otherwise, an already-configured backend on `build_<package>()` — e.g. a backend
   that reads a small *bundled* dataset (like `exampleweaver`'s CSV).

If neither is runnable, `--strict` fails with an actionable message — "skipped, no
data" is **not** a pass. Your golden inputs must be resident in whatever fixture/
bundled data you point at. `taxonweaver` is the worked example:
`build_taxonweaver_fixture()` builds a ~6-species SQLite from inline dumps
(`taxonweaver/src/taxonweaver/fixture.py`), and its golden uses organisms from that
clade — so `verify --strict` is green with no 1.2 GB build.

---

## Advanced: conform with your own plumbing

weaverkit defines a **contract**, not an implementation (decisions.md, the
unifying principle). What `verify` checks is the *manifest* (capabilities /
consumes / produces / groups / reachability), real fingerprints, and golden — **not**
that your package uses the generated `intermediate.py` / `mapper.py` / `dispatch.py`
verbatim. Two blessed patterns follow from that:

- **Bring your own dispatch/mapper/intermediate.** A rich weaver may keep
  hand-tuned internals and still conform, as long as `MANIFEST` matches the spec and
  golden passes. `taxonweaver` is the worked example: it has its own
  `BackendDispatchWeaver`, a typed `TaxonMatch`, and a resolver-specific mapper — and
  passes `weaverkit verify --strict`. The generated files are the *default* for
  simple weavers, not a requirement.
- **Typed domain record → project to `values` at the seam.** The generic mapper is
  keyed by `type_id → value` (it must stay domain-neutral). If you want real typing,
  keep a typed intermediate in your weaver (like `TaxonMatch` with `taxid`,
  `scientific_name`, …) and flatten it into `record.values` only at the mapper
  boundary. Typed where your logic lives; dynamic at the framework seam.

If you go this route, the contract you must still honor is unchanged: one record
per input in order, miss-is-data, never-`unknown` fingerprints, emit only produced
`type_id`s, and `is_configured()` reflecting data presence.

---

## Bulk-file sources: `setup.py`

If the backend reads a large bulk file (a multi-GB dump), don't commit it — add a
`setup.py` with an `ensure_<db>_db(...)` that downloads/builds it into the user
cache on first use, mirroring `taxonweaver/src/taxonweaver/setup.py`
(`ensure_taxonomy_db`: default cache path, consent gate, checksum verify, atomic
build→rename, cross-process lock). Record the source version there so `fingerprint`
can read it back. See `docs/local-db-setup-plan.md` for the full design.
