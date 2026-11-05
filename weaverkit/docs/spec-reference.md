# Weaver spec reference


Complete worked examples live in [`tests/fixtures/`](../tests/fixtures) (lookup,
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
| `weaver_id` | no | join namespace if it differs from `db_name` (ncbi_weaver's is `ncbi`). |
| `kind` | no | `"lookup"` (default, clean id→data) or `"resolver"` (fuzzy/ambiguous + candidates). |
| `api_key` | no | `"none"` (default) / `"optional"` / `"required"` — drives the API backend stub. |
| `citation`, `attribution` | no | DOI/reference and provider credit, emitted through manifest provenance. Fill them when source attribution requires them. |

**`[[capability]]`** (one or more) — `id`, `consumes` (registered shared keys),
optional `backends` / `max_batch_size` / `cost`, optional `always_computed_groups`
(group ids always computed internally, e.g. `["core"]`), optional `set_outputs`
(produced join keys that are one→many — the weaver emits a *list* and the executor
may fan out one child per value under `ExpandPolicy`; must be a subset of `produces`,
e.g. `["pathway.reactome.id"]`), optional `consumes_any` (bool — interpret `consumes`
as *alternatives*: any one input suffices and the planner routes from each one
independently, rather than the default *conjunction* of all inputs; the backend
dispatches on whichever input is present — e.g. a UniProt ID-mapping
`{gene id, ensembl id, pdb id, …} → accession`), one or more `[[capability.group]]`
(`id` + `outputs`, disjoint across groups), and optional `[[capability.parameter]]`
blocks (per-query knobs — filters/sort/thresholds — `name`, `type` ∈
`string|int|float|bool`, optional `enum`/`default`/`description`; surfaced as
`--param` in the CLI and threaded to the backend's `fetch` as `params`).

**`lists`** (optional, per capability) — the produced outputs that are lists, e.g.
`lists = ["pathway.reactome.names"]`. Maps to `Capability.lists`. They read back as a
`braidworks.Listing` (a `list` with `.total` and `.complete`), complete unless the
backend returned a partial `Listing`; exports add a `<list>.total` column. `set_outputs`
and `totals` keys count as lists without being repeated here.

**`totals`** (optional, deprecated) — `{ "<list type>" = "<count type>" }`, e.g.
`totals = { "structure.pdb.ids" = "structure.pdb.count" }`. Keeps an existing `.count`
output working as an alias: core derives the count from the list's size (omitted when
the size is unknown), so the backend no longer writes it. Both must be outputs of the
capability, in one output group (or the count in `always_computed_groups`). Every
produced `*.count` must be declared here (`verify` rejects one that is not). Don't add
new ones; name other counts for what they count, e.g.
`microbe.disease.experiment_count`.

A golden example can check a list's true size with `"<list>.total" = N` in `expect`.

**`[bulk]`** (optional) — `backend` (must be one of `backends`), `archive_url`,
`filename`: triggers the generated `setup.py` + `<db>-ensure` CLI for a multi-GB
local DB.

**`[types]`** (optional) — `"type.id" = "one-line meaning"` for types this weaver
consumes or produces. Every such type is described automatically from the key
registry (`weaverkit.keys.SHARED_KEYS` / `OUTPUT_KEYS`); add an entry here only to
override that text for this source. The resolved descriptions are generated into
`vocab.py` as `TYPE_DESCRIPTIONS` and shipped on the manifest
(`WeaverManifest.type_descriptions`), so users can search fields by meaning without
weaverkit installed. `verify` rejects entries for types the weaver does not use and
warns about types with no description anywhere, or a `vocab.py` generated before
descriptions existed.

**`[[golden]]`** (optional for `verify`; `--strict` requires ≥1) — `capability`,
`input` (keys ⊆ that capability's consumes), `expect` (keys ⊆ its produces). Under
`--strict` each runs against a fixture (`build_<package>_fixture()`) or an
already-configured backend, so pick inputs resident in that data.

