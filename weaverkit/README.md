# weaverkit

Guardrails for building Braidworks weavers, so an agent can add a database
weaver reliably instead of vibe-coding it. Three pieces:

- **spec** (`weaver.spec.toml`) — the contract an agent fills *before* coding:
  db name, source, license, capabilities (consuming **registered shared keys**),
  output groups, backends, and golden examples. Validated by `weaverkit.spec`.
- **scaffold** (`weaverkit new`) — stamps a thin weaver package from a spec (vocab,
  thin glue, backend stubs); the routing/mapping/record runtime is imported from
  `braidworks-core`, not copied. So the structure/wiring is generated, not
  hand-written, and you implement only the backends.
- **conformance** (`weaverkit verify` + `WeaverConformanceTests`) — machine checks
  that the built weaver matches its spec, is reachable (consumes a shared key),
  and never returns an `"unknown"` fingerprint.
- **index** (`weaverkit index`) — scans every `weaver.spec.toml` and writes a small
  delimited map (`weaver`, `capability`, `kind`, `api_key`, `backends`, `consumes`,
  `produces`, `unmet_inputs`) so you can see what join keys already exist and pick a
  new weaver's inputs to connect. An `unmet_inputs` entry is a hint, not an error.
- **view** (`weaverkit view`) — discovers the installed weavers (the
  `braidworks.weavers` entry points) and renders a single self-contained,
  interactive HTML file: the whole weaver network as a `type → weaver → type`
  graph, plus an optional braid path for a `--from … --to …` query (the real
  `Braider` plan, laid out by dependency wave). Set-valued (one→many) produced
  keys are badged `⤜ fan`. Pass `--run result.json` (a serialized
  `ExecutionResult.to_json()`) to add a **run-lineage view** per originating
  input — the cardinality fan-out trace, `input → fork ⤜ one leaf per value`.
  No CDN, opens offline.

The architectural decisions behind the toolkit (what's contract vs weaver freedom,
the `--strict` regimes, dispatcher/backend split) live in
[docs/decisions.md](docs/decisions.md); the resulting work is tracked in
[docs/backlog.md](docs/backlog.md).

When implementing the generated `# TODO` backend spots, see
[docs/implementing-backends.md](docs/implementing-backends.md) — the per-function
contract the stubs deep-link into. For the wider picture see
[docs/weaver-implementation-guide.md](../docs/weaver-implementation-guide.md) and
[AGENTS.md](../AGENTS.md).

## `weaver.spec.toml` field reference

Complete worked examples live in [`tests/fixtures/`](tests/fixtures/) (lookup,
resolver, and bulk). `weaverkit verify --spec ...` reports every field problem at
once, so write a draft and let it guide you. The fields:

**`[weaver]`**

| field | required | notes |
|---|---|---|
| `db_name` | yes | `^[a-z][a-z0-9_]*$`; the package becomes `<db_name>_weaver`. |
| `title`, `version`, `license`, `source_url` | yes | non-empty metadata. |
| `fingerprint_source` | yes | what versions the data (release tag / dump date / checksum); never `"unknown"`. |
| `source_sample` | yes | a **real** snippet of the source (anti-hallucination guard). |
| `backends` | yes | e.g. `["local"]`, `["local", "api"]`. |
| `weaver_id` | no | join namespace if it differs from `db_name` (taxon_weaver's is `ncbi`). |
| `kind` | no | `"lookup"` (default, clean id→data) or `"resolver"` (fuzzy/ambiguous + candidates). |
| `api_key` | no | `"none"` (default) / `"optional"` / `"required"` — drives the API backend stub. |

**`[[capability]]`** (one or more) — `id`, `consumes` (registered shared keys),
optional `backends` / `max_batch_size` / `cost`, optional `always_computed_groups`
(group ids always computed internally, e.g. `["core"]`), optional `set_outputs`
(produced join keys that are one→many — the weaver emits a *list* and the executor
may fan out one child per value under `ExpandPolicy`; must be a subset of `produces`,
e.g. `["pathway.reactome.id"]`), one or more `[[capability.group]]`
(`id` + `outputs`, disjoint across groups), and optional `[[capability.parameter]]`
blocks (per-query knobs — filters/sort/thresholds — `name`, `type` ∈
`string|int|float|bool`, optional `enum`/`default`/`description`; surfaced as
`--param` in the CLI and threaded to the backend's `fetch` as `params`).

**`[bulk]`** (optional) — `backend` (must be one of `backends`), `archive_url`,
`filename`: triggers the generated `setup.py` + `<db>-ensure` CLI for a multi-GB
local DB.

**`[[golden]]`** (optional for `verify`; `--strict` requires ≥1) — `capability`,
`input` (keys ⊆ that capability's consumes), `expect` (keys ⊆ its produces). Under
`--strict` each runs against a fixture (`build_<package>_fixture()`) or an
already-configured backend, so pick inputs resident in that data.

## Decision: the spec is TOML, not YAML

The spec format is `weaver.spec.toml`, parsed with the stdlib `tomllib`. This was
a deliberate choice over YAML:

- **No silent type coercion.** A spec is full of short identifiers, version tags,
  and accession-like strings. YAML would mangle them — `license: NO` parses to
  boolean `False` (the "Norway problem"), `version: 1.10` becomes a float and
  drops the trailing zero, `id: 09` can error on octal. TOML keeps every value
  exactly as written. For a *guardrail*, no-surprise parsing matters most.
- **Zero dependencies.** weaverkit is the package everything else trusts; keeping
  it stdlib-only (no PyYAML) is worth more here than anywhere. It also matches the
  rest of the repo — authors are already in `pyproject.toml` headspace.
- **Fails loud, not silent.** TOML errors on malformed structure; YAML often
  parses subtly-wrong input into the wrong shape (merged keys, stray tabs). For an
  agent-authored, machine-validated file, a loud parse error beats a quiet misparse.

The one cost is that the schema is nested (capabilities → groups → outputs), and
TOML's array-of-tables (`[[capability]]`, `[[capability.group]]`) is more verbose
than the YAML equivalent. That's acceptable: the nesting is only two levels deep,
and `validate_spec` turns any structural mistake into a precise error. The spec is
write-once and machine-validated in a loop, so parse-determinism and clear errors
outweigh authoring ergonomics — which is exactly where TOML wins. If this were a
human-tuned config edited daily, YAML would be the better call.
