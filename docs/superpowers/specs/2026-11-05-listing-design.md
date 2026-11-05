# Lists that know their own size (`Listing`)

Status: decisions taken, awaiting design approval · Builds on: #347 → #348 → #349 → #351 · Parent: #304 (M1, item 1.5)

## Why

A researcher using the Python API should be able to read a list result without
learning Braidworks conventions. Today a capped list arrives as up to four things
that the weaver author must keep in sync and the reader must know to combine:

| What | Example (PDBe) | Where it comes from |
|---|---|---|
| a capped display list | `structure.pdb.ids` (25 items) | the backend slices it |
| the full set (fan-out key) | `pdb.id` (all items) | `set_outputs` |
| a sibling count strand | `structure.pdb.count` = 321 | spec `totals = {list → count}` |
| a `.total` column | `structure.pdb.ids.total` | `Result` copies the count over |

On top of that, each weaver's `…coverage` dict restates the same facts in its own
words (`observed_count`, `observed_models`, `observed_strains`, `observed_products`,
`total_partners`, `displayed_models`, `display_limit`, `complete`, `source_complete`,
`count_scope`, `fan_scope`). Twelve `list_*` capabilities report no size at all.

#351 fixed what the `.count` names *mean*. This change removes the need for them:
**a list value carries its own size and completeness, defined once in core.**

The bar is #304's: Biopython-grade predictability. Biopython's objects behave like
the Python types they resemble (`len(record.features)`), and the library, not each
data source, documents their shape once.

## Prior art (what we're borrowing)

- **Biopython `Entrez.esearch`** returns `IdList` (capped by `retmax`) next to
  `Count` (the true total), as sibling dict keys. That's our current model. It's
  acceptable there because it's a faithful transcription of NCBI's XML, and it
  covers one source. Across 17 sources it falls apart, as we've seen.
- **Elasticsearch `hits.total = {value, relation: "eq" | "gte"}`.** A total can be
  exact or a lower bound. Lesson: "we stopped early" is information, so don't
  invent a number.
- **GraphQL Relay connections.** `pageInfo.hasNextPage` is required, while
  `totalCount` is an optional extension. Lesson: completeness and total are
  *separate facts*. A source can know that more exist without knowing how many.
- **PyGithub `PaginatedList.totalCount` / Django `Paginator.count`.** The total
  belongs to the collection object, not to a sibling field.

## Design

### 1. `Listing`: what a user sees

`braidworks.Listing` is a `list` subclass with two read-only attributes:

```python
pdb = row["structure.pdb.ids"]
pdb                 # ['1TUP', '2OCJ', …] (25 of 321)
len(pdb)            # 25, what we have
pdb.total           # 321, or None when the source can't tell us
pdb.complete        # False: more exist than we have
```

- `complete is True` ⇒ `total == len(listing)`.
- `complete is False, total=int` ⇒ we have a prefix of a known-size list (PDBe, NCBI).
- `complete is False, total=None` ⇒ we stopped early and the true size is unknown,
  but it's *at least* `len()` (QuickGO page cap, STRING `max_partners`). Displayed
  as `25+`.
- Because it is a `list`, everything that takes a list keeps working: iteration,
  slicing, `json.dumps`, pandas, `in`. Slicing or copying returns a plain `list`,
  because a slice no longer means "a prefix of N".

### 2. On the wire: `Strand` carries it

`Strand.value` stays a plain JSON list, so canonicalisation, joins, fan-out and the
cache codec see no new value type. Two optional fields go on `Strand`:

```python
total: int | None = None      # true size; None = unknown, or not a list
complete: bool = True
```

`to_json()` writes them only when they're not the defaults (`complete=False` or a
`total` set), and `from_json()` reads them with defaults. Old JSON and old caches
therefore round-trip unchanged. (The builder decides whether this needs a cache
schema bump. See *Left to the builder*.)

For a list-valued strand whose backend says nothing, core treats it as complete
with `total = len(value)`.

### 3. Backends: one way to say "partial"

A backend puts a `Listing` into `LookupRecord.values` / `ResolverRecord.values`
when, and only when, the list is not the whole thing:

```python
values["structure.pdb.ids"] = Listing(ids, total=hit_count)        # known total
values["go.term"] = Listing(terms, total=None, complete=False)     # stopped early
values["pathway.reactome.names"] = names                           # complete: plain list
```

The shared mapper unpacks a `Listing` into `Strand(value=list(...), total=…,
complete=…)`. This is the only place a weaver states size or completeness.

### 4. Stop capping for display inside weavers *(maintainer decided: yes)*

Today backends slice lists to 10 or 25 "for display" while separately emitting the
uncapped set key for fan-out. Capping for display is a presentation concern. Under
this design:

- Weavers return **everything they retrieved**. They cap only to bound **retrieval
  cost** (page limits, `max_partners`), and when they do, they say so with `Listing`.
- Display truncation happens once, in core's presenters (`Result` repr and HTML
  table, CLI human output #319, GUI results #326), using one shared formatter that
  renders `25 of 321` / `25+` / `321`.
- The separate capped display list and the full set key then often describe the
  same collection. Where a capability emits both an id set (`pdb.id`) and a richer
  record list (`structure.pdb.ids`, partner records with scores), both carry the
  same `total`/`complete`.

### 5. What goes away

- **`.count` strands for list totals** (`structure.pdb.count`, `go.count`,
  `protein.interaction.count`, `microbe.disease.count`, …) and the spec's
  `totals = {…}` mapping (#348) are deprecated. For one release, core derives each
  declared `.count` strand from its list's `total`, so weavers stop writing them and
  existing `want=[…count]` calls keep working. The aliases are removed before the
  PyPI release (#331).
- **The `.total` column** in `Result.rows` goes away. The row value is a `Listing`, so
  `row["x"].total` replaces it. Exports (CSV/TSV) render the list cell as today and
  add a `x.total` column only in flat exports, where an object can't carry it.
- **Count fields inside `…coverage` dicts** (`observed_*`, `displayed_*`,
  `display_limit`, `total_partners`, `complete`, `source_complete`, `count_scope`,
  `fan_scope`) are removed. Coverage keeps only source context with no core home
  (`release`, `network_type`, `scope`, `lookup_policy`, …).
- **Counts of something else stay** and keep #351's naming
  (`microbe.disease.experiment_count`, `microbe.abundance.association_count`). They
  aren't list sizes.
- **`ncbi.taxon.children_count`** becomes the `total` of `ncbi.taxon.children_records`
  (kept as a deprecated alias like the other `.count` strands).

### 6. What `verify` enforces

- Every capability with `set_outputs` or a `list_*` id must, in its conformance
  fixture, emit list strands whose `total`/`complete` are consistent
  (`complete ⇒ total == len`, `total ≥ len`).
- New specs may not declare `.count` list totals or `totals = {…}` (warning during
  the deprecation release, then an error). This replaces #351's `.count` rule. The
  "other counts are named for what they count" half of #351 stays.
- `ExpansionTruncation` (executor fan-out caps) is untouched. It describes what the
  *executor* chose not to follow, not what a source returned.

## Goals / non-goals / anti-goals

**Goals:** one obvious way to read a list's size from Python, CLI and GUI; one
place a weaver states it; every list capability covered, not just the 9 with
`totals`; backwards compatibility for one release.

**Non-goals:** pagination (fetching "the next 25"); changing fan-out policy;
redesigning `coverage` beyond removing its counts.

**Anti-goals:** a wrapper users must unwrap to get a list (`listing.items`); a
`Listing` that silently claims `complete=True` for a list a weaver capped; any
per-weaver vocabulary for size.

## Rollout

1. Merge #347 → #351 as they are. Their *semantic* fixes (STRING fetches all
   partners, QuickGO omits an understated total, Disbiome/GMrepo counts mean
   diseases/phenotypes) carry over unchanged. Only the plumbing is replaced.
2. **PR A (core):** `Listing`, `Strand.total/complete`, mapper unpacking,
   `Result` rows return `Listing`, the shared formatter, the derived `.count`
   aliases, the `verify` rule. Core minor bump (`braidworks-core>=0.x.0` floor for
   weavers that adopt it).
3. **PR B (weavers, can be split per weaver):** each backend emits `Listing` where
   partial, drops display slicing and coverage counts, spec drops `totals`. Patch
   or minor bump per weaver as AGENTS.md requires (three version sites).
4. **PR C (docs):** folded into #313 (M1 Python API docs): one page explaining
   `Listing`.

## Maintainer decisions

1. **Weavers stop display-capping (§4).** Weavers return everything they retrieved.
   Core presenters shorten it on screen.
2. **`.count` aliases are kept for one release**, derived by core from the list's
   `total`, and removed before the PyPI release (#331).

## Settled after review (designer's calls; the maintainer can override)

- **Which lists become a `Listing`.** Only strands whose type is a capability's
  `set_outputs` key or a list the backend returned as a `Listing`. Other list values
  (synonyms, coordinates, `candidates`) stay plain lists, so there's no `Listing`
  noise and no extra export columns for them. The capability already knows its
  `set_outputs`, so no new registry marker is needed. A non-set display list that
  can be partial is marked by the backend returning a `Listing`.
- **Fan-out.** `total`/`complete` stay on the parent's set strand, which is what's
  displayed for the input row. Children carry one scalar member and no
  `total`/`complete`. `ExpansionTruncation` keeps reporting executor caps separately.
- **Merging.** `total`/`complete` belong to the strand. Whichever strand wins under
  the `MergePolicy` brings its own values, so they are never mixed across strands.
  The same goes for every copy site (`StrandSet`, cache, `to_json`): they copy the
  strand whole.
- **Readers of coverage count fields.** `git grep` finds them only in the weavers'
  own backends and tests, `quickgo_weaver/REFERENCE.md`,
  `docs/tutorials/disease-associations.md` and an internal audit probe file. No
  core, GUI or network-view code reads them. PR B updates those weaver tests and
  docs in place, with no deprecation step. (`wikipedia_weaver/measurement.py`
  matches on `observed_` for an unrelated meaning and is out of scope.)
- **How strict `verify` is.** It enforces *consistency* (`complete ⇒ total == len`,
  `total ≥ len`) on fixture output. It can't detect a silent cap on its own, so
  golden examples gain an optional expected `total` (e.g.
  `expect = { "structure.pdb.ids" = { total = 321 } }`), and live E2E tests assert a
  known-truth total. That catches a backend that capped without saying so. A
  PITFALLS entry ("cap only with a `Listing`") covers the rest.

## Left to the builder

- Whether `Strand.total/complete` needs a cache schema/version bump so that old
  cached capped lists aren't read back as complete. (If old entries can't be told
  apart, bump.)
- Exact `repr` of `Listing`, and whether `Listing` is also exported from
  `braidworks.core`.
- How the CLI/GUI formatter abbreviates long lists. It must use the shared formatter.
- Splitting PR B per weaver vs one PR.
