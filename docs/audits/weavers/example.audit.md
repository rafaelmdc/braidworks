# Example weaver audit

Date: 2026-10-08. Source revision: `d5e7543`; package `1.0.3`, core floor `0.1.8`.
Status: audited locally; recommendations proposed. This is a teaching fixture,
not an external scientific database. Database popularity research is inapplicable.

## Main findings

| ID | Priority | Finding | Evidence and impact | Recommendation |
|---|---|---|---|---|
| WV-EXAMPLE-001 | P1 | Contributor regeneration advice can destroy implemented backend code | CONTRIBUTING steps say backend code survives `new --force`; current `scaffold.write_files` overwrites generated backend paths | Replace advice with scratch generation, diff and selective application |
| WV-EXAMPLE-002 | P2 | Unknown builder configuration is silently discarded | `factory.build_example_weaver(**config)` never reads config; reproduced `misspelled_setting='ignored'` | Reject nonempty unsupported configuration at the public boundary |
| WV-EXAMPLE-003 | P2 | Teaching prose overstates scaffold equivalence and lacks a complete execution example | README says literally the generated scaffold with TODOs filled; Example omits discovery deliberately and uses a worked CSV backend; example only constructs a weaver | Explain intentional differences and demonstrate execution, missing results and output selection |
| WV-EXAMPLE-004 | P2 | Contract sample inputs are unfinished despite five bundled real rows | `TestLocalOrder.sample_strand_sets` contains 562/1423 plus sample-0/1/2 and a TODO; actual table also has 1280/1773/1351 | Use all five real IDs; retain separate miss and duplicate cases |
| WV-EXAMPLE-005 | P2 | Published source metadata is not a usable canonical URL | spec/vocab source_url contains old owner `rafaelcorreia` plus explanatory text | Use canonical repository data-file URL; keep explanation in attribution/docs |
| WV-EXAMPLE-006 | P3 | Parsing and resource I/O share a cached mutable table | `_load_table` reads, parses and caches nested mutable dictionaries; no parser-specific tests | Optionally extract a pure parser with explicit header/duplicate rules; keep cached data private |

001–005 are verified by code inspection and the probes below; 006 is a supported
maintainability recommendation, not a reproduced production corruption.

## Current capability and teaching coverage

| Task | Current support | Limits |
|---|---|---|
| Describe traits for taxid | Full, local CSV, `describe_traits` | Five illustrative rows; not a biological knowledge base |
| Select core/growth outputs | Full through core mapper | Backend cheaply computes both fields; appropriate at this scale |
| Batch distinct/duplicate inputs | Verified | Input order preserved; no upstream I/O |
| Missing/absent taxid | Verified NO_MATCH | No fabricated traits |
| Zero-config offline construction | Full | Bundled resource, stable explicit DATA_VERSION |
| Automatic CLI/browser discovery | Intentionally absent | No entry point; register explicitly in Python |
| Learn a complete execution workflow | Partial | README only builds the weaver; no result example |
| Learn extension/regeneration safely | Incorrect advice | Backend overwrite risk in CONTRIBUTING |

## Architecture and design assessment

Responsibility chain: provider delegates construction → factory composes local
backend → `ExampleWeaver` declares manifest/mapper → shared `BackendDispatchWeaver`
validates and dispatches → backend looks up records → pure core mapper selects strands.
This is an appropriate small template-method runtime with composed backend strategy.
Retain it. A separate repository class, abstract CSV backend hierarchy or service
container would add indirection without a concrete need.

Functional improvement is modest: separate `parse_traits(text)` from resource loading
if parser validation is added. Establish required headers, duplicate-ID behavior and
missing-cell handling. Do not introduce a public dataclass solely for two strings.
Returned `values=dict(values)` already protects the cached row from caller mutation;
the module-private table itself remains mutable. Frozen public records or a generic
CSV repository are not necessary for this reference.

The builder's unused `**config` undermines an explicit contract. An empty-config
provider remains useful; unknown settings should produce a clear structural error.
Any shared scaffold change needs evidence from other packages, not just this example.

## Build, correctness and usability checklist

- **Source and biological semantics:** synthetic/illustrative bundled sample,
  taxid-keyed string values; README labels teaching use. Further biological inference
  capabilities are inappropriate. Document units for optimum temperature and that
  source/license metadata are illustrative, not independent experimental evidence.
- **Capabilities/parameters:** one lookup, two groups; no parameters or fuzzy matches.
  `resolve` candidates, pagination and fan-out are inapplicable.
- **Batching/error handling:** loop over in-memory lookups is appropriate; no network.
  Missing taxid becomes NO_MATCH. Backend ignores capability_id because shared
  dispatch validates the single capability; no extra strategy registry warranted.
- **Build/update lifecycle:** no external build/download, DB, connection or local/API
  parity requirement. `importlib.resources` supports installed package resources.
  DATA_VERSION requires a manual bump when CSV changes; teach this rule explicitly.
- **Connectivity:** consumes registered NCBI taxid; produces trait leaves. Teaching
  example deliberately stays out of discovery; do not add a CLI entry point just to
  equalize it with production sources.
- **Documentation:** CONTRIBUTING expansion notes are generic filler; explain the
  concrete column table, CSV shape, output groups and fingerprint update workflow.
  Distinguish data CC0 and software MIT, which README already does correctly.
- **Verification:** conformance/contract/golden tests pass. Golden cases cover two
  rows; order contract's three fabricated misses cannot prove all five successful
  identities are preserved. Strict completion is not a guarantee that tests contain
  no TODO comments: its source-placeholder scan does not enforce this test TODO.
- **Scaffold comparison:** generated scratch snapshot contains 15 artifacts; current
  teaching package intentionally differs. No generated files applied to live package.

## Reproductions and acceptance evidence

Commands executed in isolated existing environment on 2026-10-08:

```bash
UV_PROJECT_ENVIRONMENT="$PWD/.audit-local/tools/venv" UV_NO_SYNC=1 \
  make -C weavers/example_weaver test
.audit-local/tools/venv/bin/weaverkit verify \
  --spec weavers/example_weaver/weaver.spec.toml --package example_weaver --strict
```

Results: **19 passed**, no skips; strict conformance/no-placeholder/golden gate passed.
Scratch probe executed all five real IDs, duplicate 562, absent ID and null ID in one
batch requesting only gram stain: six correctly ordered successes then two NO_MATCH;
no optimum-temperature strands leaked into requested output. Builder with a made-up
setting completed without warning.

Pure `generate_files(load_spec(...), spec_toml=...)` wrote comparison artifacts only
under `.audit-local/example-scaffold-baseline`. Actual backend SHA256
`b971fd28c85539c0c32f178330dc061cd5c64264d352c63317378c86e07c0cd9` differs from generated
stub `bf8ebe63a3d69c96176cc7d0125b6b5bde273481ac4838af8aa14160b8ac62df`. Combined with
the overwrite implementation this verifies the stale instruction risk without
overwriting user code. Previous final acceptance covers installed resource inclusion;
it was not repeated for this documentation-only audit.

## Evidence pointers and disposition

Inspect [backend](../../../weavers/example_weaver/src/example_weaver/backends/local.py),
[factory](../../../weavers/example_weaver/src/example_weaver/factory.py),
[contract tests](../../../weavers/example_weaver/tests/test_contract.py),
[README](../../../weavers/example_weaver/README.md),
[CONTRIBUTING](../../../weavers/example_weaver/CONTRIBUTING.md),
[spec](../../../weavers/example_weaver/weaver.spec.toml) and
[generator](../../../weaverkit/src/weaverkit/scaffold.py).

Proceed with teaching/correctness polish after review. Defer parser extraction unless
it improves the lesson or validation; reject unrelated database features and new
framework abstractions. See [proposed spec](example.spec.md) and [plan](example.plan.md).
