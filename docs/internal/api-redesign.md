# Researcher API redesign

Status: accepted (decisions recorded at the end). Scope: the Python API first, then the CLI and the browser on top of it.
Nothing here removes an existing name; `braidworks.core` keeps working as it does today.

## Problem

A researcher's first contact with Braidworks should look like `mygene.querymany` or
`gget.info`: a list of IDs in, a table out, the same words in Python and on the command
line. Today it does not:

| Observation | Where |
|---|---|
| `fetch(want, ids, have=…)` puts `want` first; the CLI says `--have … --want …`. | `core/fetch.py` |
| `have` defaults to `ncbi.taxon.id`, a biology assumption in the domain-neutral core, and silently wrong for every non-taxon query. | `fetch.DEFAULT_HAVE` |
| `only=` must be a `frozenset`; parameters must be a nested `params={…}` dict. | `fetch` |
| `fetch` calls `asyncio.run`, so it fails inside Jupyter, where most analysis happens. | `fetch` |
| `fetch` discovers a fresh registry per call and never closes its weavers' HTTP clients. | `fetch` (no `aclose`) |
| No table output: results are `{id: {type: value}}` dicts; the CLI and browser each build their own rows. | `fetch`, `cli._result_records`, `serve` |
| `braidworks.core` exports 123 names for three audiences at once: researchers, weaver authors (`BackendBase`, `map_lookup`) and internals (`md5_file`, `check_disk`, `BuildLock`). | `core/__init__.py` |
| Anything beyond `fetch` needs `AsyncExitStack`, `BraidRegistry`, `Braider`, `LocalExecutor`, `StrandSet.from_strands` and `entity.get(key).value`. | `docs/usage.md` |
| The CLI, the browser server and `fetch` each wire plan → execute → flatten themselves. The server alone has three run paths (plain, traversed, batch/persistent). | `cli.py`, `weaverkit/serve.py` |
| Results label inputs `e1`, `e2` instead of the value the user typed. | CLI human output |

## Principles (from comparable packages)

- **One vocabulary everywhere** (gget): every task has the same name and arguments in
  Python, the CLI and the browser.
- **IDs in, table out** (mygene `querymany(..., as_dataframe=True)`, g:Convert): rows keyed
  by the input value, an "input" column next to the requested ones.
- **Simple call, explicit session when needed** (requests: `requests.get` vs
  `requests.Session`): module functions use a shared default session; a `Session`
  holds configuration (cache, sources, backend policy) and owns resource cleanup.
- **Configure once** (Biopython `Entrez.email`): cache paths and policies live on the
  session, not on every call.
- **Honest results by default**: missing, review and error outcomes are visible in the
  summary, never only in a side list.

## Three layers

| Import | Audience | Contents |
|---|---|---|
| `braidworks` | Researchers | `get`, `find`, `path`, `sources`, `Session`, `Result`, `fetch` (unchanged, compatible) |
| `braidworks.weaver` | Weaver authors | Re-exports of `BackendBase`, `BackendDispatchWeaver`, `LookupRecord`, `ResolverRecord`, `map_lookup`, `map_resolver`, `is_not_found_status`, download/local-DB helpers |
| `braidworks.core` | Engine and integrators | Everything, as today |

`braidworks.weaver` is a re-export module only; nothing moves, so no weaver changes.

## One task, one name

| Task | Python | CLI | Browser |
|---|---|---|---|
| Check the installation | `bw.sources()` | `braidworks doctor` | Status line in the header |
| Find a field by meaning | `bw.find("pdb structures")` | `braidworks find pdb structures` | Search box on "What do you want?" |
| Preview a route | `bw.path(have, want)` | `braidworks path --from … --to …` | "How this is answered" panel |
| Run a query | `bw.get(ids, have=…, want=…)` | `braidworks get IDS --have … --want …` (`weave` stays as an alias) | Run button |
| Follow a relationship | `bw.get(…, for_each="orthologs")` | `--for-each orthologs` | "For each…" option |
| Resolve ambiguity | `result.review[i].choose(k)` then `result.continue_()` | `braidworks runs` / `resume` | Review tab |
| Cite sources | `result.references`, `result.cite()` | `braidworks references` | Footer of the results |
| Export | `result.to_pandas()`, `.to_csv(path)` | `--format csv` | Download button |

## `get`

```python
import braidworks as bw

result = bw.get(
    ["P04637", "TP53"],
    have="protein.query",
    want=["protein.name", "structure.pdb.ids"],
    organism="9606",
)
result                 # notebook: summary + table
result.to_pandas()     # one row per input (or per expanded child)
```

```python
def get(
    ids,                         # str | Iterable[str] | Mapping[type, Iterable] | DataFrame | Path
    *,
    have: str | None = None,     # required unless ids carries type-named columns
    want: str | Sequence[str],
    expand: str = "none",        # "none" | "all" | "top:5"   (same strings as the CLI)
    for_each: str | None = None,
    sources: Iterable[str] | str | None = None,   # replaces only=frozenset(...)
    review: str = "halt",        # "halt" | "allow_continue" | "raise"
    min_confidence: float = 0.0,
    params: Mapping | None = None,  # scoped form: {"resolve_protein": {"organism": "9606"}}
    session: Session | None = None,
    **parameters,                # bare capability parameters: organism="9606"
) -> Result
```

- **Inputs.** A string or list of strings needs `have`. A mapping, a DataFrame or a
  CSV/TSV path with type-named columns supplies its own types per row, matching the CLI's
  `--in-file`. Duplicate inputs stay separate rows (the CLI's behaviour), unlike `fetch`.
- **No silent default for `have`.** Omitting it with plain strings raises a `ValueError`
  that lists the installed input types closest to the values' apparent shape and points
  to `bw.find`.
- **Parameters as keywords.** Unknown keywords are validated against the route's declared
  parameters before any source call, with a did-you-mean (the diagnostics from #301).
  Names that collide with `get`'s own arguments go through `params=`.
- **Works in Jupyter.** If an event loop is already running, `get` runs the query on a
  worker thread and returns the result; `async_get` is the native coroutine.
- **Strings, not enums.** Options accept the CLI's strings; the enums stay accepted.

## `Result`

One flattened row schema shared by Python, CLI exports and the browser, built once from
`execution_records`:

| Column | Meaning |
|---|---|
| `input` | The value the user supplied (not `e1`) |
| `row` | Input position, so duplicates and file rows stay distinct |
| `parent` | For expanded children, the input they came from |
| `status` | `resolved` / `missing` / `review` / `error` |
| `<want type>` … | One column per requested type |
| `missing` | Requested types this row did not get |

```python
result.summary()        # "2 inputs · 1 resolved · 1 needs review · 0 errors"
result.rows             # list[dict] in the schema above
result.to_pandas()      # optional dependency: braidworks[pandas]
result.to_csv(path)     # also to_tsv / to_json
result.column("protein.name")   # {input: value}, as FetchResult.column does now
result["P04637"]        # rows for one input
result.missing          # rows without every requested value
result.review           # items with .candidates and .choose(k) / .accept() / .reject()
result.errors           # diagnostics, already explained in plain words
result.references       # citations for the sources used
result.cite()           # formatted reference list (text; bibtex later)
result.route            # the plan that ran, printable like `braidworks path`
result.raw              # the underlying ExecutionResult, for engine users
```

Collections (for example `structure.pdb.ids`) stay list values in `rows`; `to_pandas`
keeps them as list columns, and `to_pandas(explode="structure.pdb.ids")` gives one row
per member. Truncated lists carry their true total (`"25 of 312"` in the human view).

## `Session`

```python
with bw.Session(
    sources=["uniprot", "pdbe"],
    cache="~/.cache/braidworks/lookups.sqlite",
    backend="api_first",
) as s:
    r1 = s.get(ids, have="protein.query", want="protein.name")
    r2 = s.get(r1.column("protein.uniprot.accession").values(),
                 have="protein.uniprot.accession", want="structure.pdb.ids")
```

- Discovers and builds weavers once, reuses them across calls and closes them on exit.
  The module-level functions use a lazily created default session closed at interpreter
  exit, which fixes `fetch`'s per-call rediscovery and unclosed clients.
- Holds `QueryPersistence` (cache, run store) and the backend policy, so calls stay short.
- `s.get`, `s.find`, `s.path`, `s.sources` mirror the module functions.

## `find`, `path`, `sources`

```python
bw.find("pdb structures")
# structure.pdb.ids    Experimental PDB structures of this protein.   (pdbe)  from protein.uniprot.accession
# pdb.id               ...
bw.path("protein.query", "structure.pdb.title")   # Route; prints like the CLI
bw.sources()                                       # the doctor report as data
```

`find` ranks types by name and description. Descriptions travel with the weaver that
uses the type, so core stays domain-neutral and a weaver installed with plain `pip` (no
`weaverkit`) still describes itself:

- `WeaverManifest` gains an optional `type_descriptions: dict[str, str]` (additive,
  round-trips through JSON; empty for old weavers).
- The spec may declare `[types]` descriptions for types the weaver produces or consumes.
  Codegen fills every other consumed/produced type from `weaverkit`'s `SHARED_KEYS`, so the
  registry stays the single source of truth and specs only override when needed.
- `verify` warns when a produced type has no description from either place.
- `find` merges descriptions across installed manifests and falls back to the type name.

## One execution service

Add `braidworks.core.service.run(session, request, *, on_event=None) -> ExecutionResult`
covering plain, traversed, batch and persistent queries. `get`, `fetch`, the CLI's
`weave`/`resume` and the browser server's three `/api/run*` paths all call it. This is the
change that keeps the three interfaces consistent; it also shrinks `serve.py`.

## Compatibility

- `fetch`/`async_fetch` and `FetchResult` keep their signatures and behaviour, including
  `DEFAULT_HAVE`, and are reimplemented on the service. The docs move to `get`;
  `fetch` gets a deprecation note in a later release, not a warning now.
- `braidworks.core` exports are unchanged.
- CLI flags stay. `braidworks get` is the documented command; `weave` remains an alias.
  Both accept positional IDs with a bare `--have TYPE`.

## Delivery

1. **Python API**: `service.run`, `Session`, `Result`, `get`/`async_get`, `path`,
   `sources`, `braidworks.weaver`; `fetch` delegates. Tests per function, plus a
   notebook-loop test. Core minor bump.
   **1b. Descriptions and `find`**: `WeaverManifest.type_descriptions`, spec `[types]`,
   codegen fill from `SHARED_KEYS`, regenerate vocab for every weaver (patch bumps),
   `bw.find` / `braidworks find`.
2. **CLI**: commands use the service; `get` command (`weave` alias); positional IDs;
   help split into common and
   "Advanced" groups (cache, runs, lease); `find`; `braidworks serve` alias; human output
   labelled by input with list totals.
3. **Browser**: form-first page (have → want → run → table) on the service; graph as a
   secondary panel; advanced settings collapsed; recipes become an examples gallery.

## Decisions

1. **Verb: `get`.** The common convention in bioinformatics clients and HTTP libraries
   (`mygene.getgene`, `requests.get`); clearer to newcomers than `weave`. The CLI gains
   `braidworks get`; `weave` stays as an alias. "Weave" remains the project's name for
   the routing idea.
2. **pandas: optional** (`braidworks[pandas]`). `to_pandas()` raises an install hint
   when it is missing; `rows` and `to_csv()` need no extra dependency.
3. **Type descriptions: on the manifest**, generated from the spec with `SHARED_KEYS` as
   the default text. Chosen for the long term because it works for any installed weaver,
   including third-party ones without `weaverkit`.
4. **No `have` inference.** Callers name the input type; a missing `have` is an error
   with suggestions.
