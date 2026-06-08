# weaverkit design decisions

ADR-style record of the architectural decisions behind weaverkit. Most were forced
by reshaping the real `taxonweaver` onto the backbone (the migration acted as an
acceptance test) — that surfaced the difference between a *toy* weaver and a real
one with two backends, a multi-GB dataset, and resolver semantics.

**Unifying principle (read this first).** weaverkit defines a thin **contract** and
stays agnostic about **implementation**:

- **Contract** (weaverkit owns it): the manifest (capabilities / consumes /
  produces / output groups), shared-key reachability, map-shaped strands
  (`type_id → value`), the `is_configured` / fingerprint / golden conventions, and
  the `build_<package>()` introspection entry point.
- **Implementation** (the weaver owns it): typed domain records, custom dispatch,
  how a backend fulfills a request, fixtures. A weaver may use the generated
  plumbing *or* bring its own, as long as it **conforms to the contract**.

This principle settles B, G, and F. E is the exception: "done" must be a hard,
reproducible rule, not a freedom.

---

## Already implemented (during the migration)

These are decided and landed; listed for completeness.

- **A — always-computed groups.** A capability may declare
  `always_computed_groups` (e.g. a resolver always computes `core` before
  `lineage`); the generated mapper unions them into `computed_groups` so the cache
  key isn't under-reported. *(Mapper stays generated; the fact is declared.)*
- **C/D — two-builder convention.** `build_<package>()` is the zero-config
  *introspection* builder that `verify` calls (backends present, possibly
  unconfigured); a domain-named builder (e.g. `build_ncbi_weaver(...)`) is the
  *configured* one. `weaver_id` may differ from the package name freely.
- **H — backbone backend construction.** Backends construct cheaply and never raise
  for missing data; `is_configured()` reports data presence; the dispatch gates on
  it. The hard "build it" error lives in the configured builder path.
- **I — graceful verify.** A misnamed builder yields a fix-oriented `BuilderNotFound`
  message, not a traceback.
- **K — fingerprint guard.** `backend_fingerprint` returns `unconfigured:<backend>`
  unless `is_configured()`, because `fingerprint()` may read the data source.

---

## B — Request interpretation lives in the dispatcher; fulfillment strategy in the backend

**Decision.** The dispatcher pre-resolves the *interpretation* of a request and
hands the backend a normalized instruction; the backend owns only the *strategy*
for fulfilling it.

**Why.** Today backends receive raw `requested_outputs` and must re-derive
`triggered_groups` and the "empty means all" rule — logic that already lives
authoritatively on `Capability`. Duplicating it into every backend means each can
get it subtly wrong, independently. Split by the *kind* of knowledge:

- **Request protocol** (which groups are triggered; empty = all) → **dispatcher**.
  It passes a resolved `groups_to_compute: frozenset[str]` (already expanded).
- **Data strategy** (lineage is a JOIN locally but a second API call remotely) →
  **backend**, keyed off declared group membership, never off re-parsing the request.

`requested_outputs` is still passed for output filtering, but backends stop
interpreting the request protocol.

## E — `--strict` is "logic proven against a declared fixture"; data availability never changes the outcome

**Decision.** Three formally separated regimes:

1. **`verify`** — structural only (manifest / reachability / fingerprints). Golden
   *may* skip; that's fine (it doesn't claim done-ness).
2. **`verify --strict`** — no placeholders **+ golden runs against a required
   fixture**. A synthetic fixture dataset is **first-class** (the preferred
   substrate): golden tests the mapping/resolution logic, not dataset completeness.
   "Skipped because no external data" is **invalid** under `--strict` (you owe a
   fixture) — not a silent pass.
3. **live / E2E** — opt-in, environment-gated (e.g. `BRAIDWORKS_RUN_LIVE`), tests
   production data. **Never** part of `--strict`.

**Why.** Tying "done" to whether production data happened to be present in CI makes
it non-reproducible, which defeats the purpose. Production-data correctness is a
separate concern and must not masquerade as definition-of-done.

## G — Dynamic `values` map at the core boundary; typed records in the weaver

**Decision.** Keep the generic mapper keyed by `type_id → value` (`values:
dict[str, Any]`). Typed domain records (like taxonweaver's `TaxonMatch`) live in
the **weaver**, projected into the map only at the mapper seam.

**Why.** A typed record *in core* would force core to know domain types — breaking
the domain-neutrality invariant. But typing shouldn't be lost: rich weavers keep a
typed intermediate and flatten at the edge. The generated `values`-dict record
stays the fine default for simple weavers. ("Bring your own typed record, project
at the seam" is blessed, same as B.)

## F — Produced non-shared fields are visible outputs but not join-eligible

**Decision.** Visibility ≠ join-eligibility. Non-shared produced fields are allowed
as opaque/leaf outputs, are already visible in the index's `produces` column, and
become consumable by another weaver only when **promoted to a shared key** (a
deliberate edit to `keys.py`).

**Why.** "Join keys" (must be registered for reachability) and "leaf/payload
outputs" (emitted, nothing joins on them) are different things; forcing every
produced field into the shared registry would pollute it and blur its one job.
Deliberate promotion is how we avoid accidental islands and naming drift.

**Resolution:** implemented `weaverkit.keys.OUTPUT_KEYS` (a naming catalog of leaf
outputs) + `is_known_output()`; `weaverkit index` prints a non-failing advisory for
produced fields in neither `OUTPUT_KEYS` nor `SHARED_KEYS`. Catalog membership grants
no join-eligibility — promote to `SHARED_KEYS` for that.

---

## Resulting work

See `weaverkit/docs/backlog.md` for the concrete, prioritized tickets these
decisions produce.
