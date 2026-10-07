# A06 implementation plan: scaffold generation and validated writes

Matching [specification](scaffold.spec.md); parent [application plan](application.plan.md).
Tracking: #145, #146. Date: 2026-10-08. Status: planned, not implemented.
Branch: `refactor/persistence-foundations`. Execute A06 before A07; no agents or
parallel edits are required. Package publication remains deferred.

## Order and review boundaries

| Step | Requirements | Concrete result | Checks |
|---|---|---|---|
| S01 | SC01, SC04 | Destination-independent generate_files; scaffold compatibility facade | Deterministic mapping, no I/O, artifact variants, existing scaffold suite |
| S02 | SC02 | Single-pass binding plus Python/TOML context encoders | Literal placeholders and hostile delimiters round-trip through real artifacts |
| S03 | SC03, SC04 | Complete content validation and destination preflight; explicit write_files | Fail before mutation, force conflicts, invalid paths, symlink refusal |
| S04 | SC04, SC05 | Documentation, installed-package checks, version and integrated evidence | Force wording, formatter behavior, wheel/sdist generation, workspace and lint |

These are implementation slices, not additional GitHub issues. S01–S03 can form
separate coherent local commits if their wrappers remain functional and tests pass.
Do not commit an extraction with a knowingly broken facade or claim safety gates
before S03 is implemented.

## S01 — Extract the pure generation boundary

1. Inventory templates and programmatic generators, mapping every current artifact
   and backend-selection branch. Record which tokens are code, names or free text.
2. Extract current artifact selection into generate_files with relative Path keys;
   keep the existing template constants and source generator helpers in this module.
3. Apply validate_spec for direct callers, translating returned errors to ScaffoldError.
   Establish exact raw-spec preservation and deterministic newline rules.
4. Have scaffold call generation and the write boundary, preserving its signature,
   returned paths and existing force/format defaults.
5. Extend existing variant tests to compare artifact shape and exercise generation
   without writes; keep import/manifest/conformance tests unchanged.

Exit: valid fixtures generate the same logical packages; all current scaffold tests
pass. This step alone does not satisfy prevalidated-write acceptance.

## S02 — Fix binding and encoding at the actual insertion sites

1. Reproduce the existing repeated-substitution defect with the audit example.
2. Implement original-template-only placeholder matching with named missing-token
   diagnostics. Pass artifact context from generation; unused context entries are valid.
3. Audit every user-text insertion in _PYPROJECT, Python templates, README/worklists,
   setup/ensure and backend hints. Use repr-style complete Python literals and a stdlib
   TOML string encoder where data belongs; adjust template delimiters accordingly.
   Avoid replacing one universal token with an escape that breaks another target.
4. Handle multiline prose in Python docstrings/comments explicitly; preserve semantic
   metadata in vocab and pyproject. Keep generator-produced snippets structural.
5. Test real artifacts with placeholder-looking title/citation/source values, quotes,
   backslashes, Unicode and multiline values. Parse/compile and compare resulting
   metadata; no generated source execution is needed to validate syntax.

Exit: original placeholders bind once, inserted values remain literal, metadata
round-trips and all existing generation variants remain valid.

## S03 — Validate before mutation, then publish

1. Implement complete-map validation: relative paths, traversal, normalized collisions
   and parent-file collisions; compile Python and parse TOML without imports.
2. Preflight destination and every planned target before any mkdir/write. Preserve
   no-force refusal of nonempty directories. Reject symlinks in existing path
   components and directory/file mismatches even with force.
3. Expose write_files as the sole filesystem boundary. It repeats validation/preflight
   for direct users; scaffold delegates without bypassing it.
4. Write UTF-8 text, retain unrelated files, return sorted written paths and invoke
   the best-effort formatter only after successful publication.
5. Add regressions with a preexisting sentinel/backend implementation, a late target
   conflict and injected malformed last artifact: failures preserve all bytes.
   Cover missing destinations, force, path traversal and symlink cases.
6. Inject an ordinary write failure to prove it surfaces rather than being swallowed
   by formatter fallback; document possible partial output without pretending rollback.

Exit: SC03's no-mutation guarantee holds for generation/validation/preflight failures;
ordinary write failures have the documented partial-publication limit.

## S04 — Documentation and final acceptance

1. Update toolkit scaffold API docs and generated CONTRIBUTING instructions: force
   can replace implemented generated paths; advise review/backups rather than claiming
   backend preservation. Explain generation versus writing and nontransactional limits.
2. Patch-bump weaverkit, update/sync lock in the existing isolated environment.
   Keep core and weaver versions/floors unchanged unless a real runtime change demands it.
3. Run targeted scaffold and CLI tests, the full toolkit suite, workspace make test
   and make lint. No contract relaxation; fix generated code when checks fail.
4. Build current toolkit wheel/sdist, validate metadata/resources, install into a clean
   temporary venv with its declared minimum core 0.20.0. From outside the checkout,
   generate/import lookup and resolver packages and an API/bulk variant; inspect
   emitted metadata and conformance. Network clients remain mocked/unconfigured.
5. Record actual counts, artifact/installation evidence, compatibility choices and
   commit hashes here and in the parent plan. Mark A06/AP06/W07 verified only after
   acceptance passes. Update #145/#146; leave remote delivery open.

## Verification matrix

| Boundary | Required evidence |
|---|---|
| Pure generation | Stable path/content map; no writes/subprocess; invalid semantic specs reported |
| Rendering | Original-template single pass; missing binding; literal placeholder values |
| Target languages | Python compile and TOML parse; metadata equality with quoted/multiline values |
| Writes | No-force refusal; force regular overwrite; unrelated files retained |
| Preflight failures | Existing bytes unchanged, new destination absent, late conflicts caught |
| Path handling | Traversal/absolute/colliding paths and symlinks refused |
| Variants | Lookup/resolver; local/API key none/optional/required; bulk setup/ensure |
| Contracts | Manifest/parameters/groups/fan-out fidelity; fresh-stub TODO gate preserved |
| Formatting | Off/absent/error behavior remains best effort after successful writes |
| Distribution | Clean installed-wheel generation/import at actual core floor; sdist complete |

## Implementation evidence

Pending. This planning commit changes documentation only and does not implement A06.
