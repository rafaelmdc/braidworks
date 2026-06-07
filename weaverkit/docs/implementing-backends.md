# Implementing a weaver backend

This is the reference for the `# TODO` spots in a scaffolded weaver's
`src/<db>weaver/backends/<backend>.py`. The scaffold generates everything else;
you implement a backend by filling in three things — `is_configured`,
`fingerprint`, and `fetch` — plus adding golden examples to the spec.

Each generated `# TODO` links to the matching section below. Read only the section
you're working on; the [wiring overview](#how-it-all-wires-together) explains how
your backend fits the rest and is the same for every weaver.

---

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

Example (local SQLite, single-input capability keyed on `ncbi.taxon.id`):

```python
async def fetch(self, capability_id, queries, *, requested_outputs):
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
They **skip** while the backend is unconfigured, so add them alongside `fetch`. Pick
inputs whose answers are stable and you can verify against the source.

---

## Bulk-file sources: `setup.py`

If the backend reads a large bulk file (a multi-GB dump), don't commit it — add a
`setup.py` with an `ensure_<db>_db(...)` that downloads/builds it into the user
cache on first use, mirroring `taxonweaver/src/taxonweaver/setup.py`
(`ensure_taxonomy_db`: default cache path, consent gate, checksum verify, atomic
build→rename, cross-process lock). Record the source version there so `fingerprint`
can read it back. See `docs/local-db-setup-plan.md` for the full design.
