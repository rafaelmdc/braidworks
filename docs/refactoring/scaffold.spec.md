# A06 specification: deterministic scaffold generation and validated writes

Matching [implementation plan](scaffold.plan.md). Parent:
[AP06](application.spec.md#ap06--scaffold-functional-core-and-publication-shell),
[A06](application.plan.md#a06--scaffold-functional-core-and-publication-shell).
Tracking: [#145](https://github.com/rafaelmdc/braidworks/issues/145),
[#146](https://github.com/rafaelmdc/braidworks/issues/146).
Date: 2026-10-08. Status: specified; implementation not started.

## Problem and observed behavior

The current scaffold generator in `weaverkit/src/weaverkit/scaffold.py` selects
artifacts, creates token dictionaries, renders, writes and formats in `scaffold()`.
Its destination-bound mapping makes generation difficult to inspect without writes.
No complete Python/TOML validation occurs before writing.

`_render()` repeatedly applies `str.replace`. Reproduction:
`_render("title={{TITLE}}", {"TITLE": "literal {{VERSION}}", "VERSION": "0.1.0"})`
currently returns `title=literal 0.1.0`. This proves repeated substitution; it does
not establish an exploit or a broken complete package. Some templates insert
free-form titles, URLs and descriptions into quoted Python/TOML source without
context-specific encoding, so quotes, backslashes and newlines need explicit coverage.

The CLI validates the spec before calling scaffold; direct callers do not receive
that guard. Without force, an existing nonempty destination is rejected. Force writes
generated paths, including backend files, and leaves unrelated files in place.
Formatting runs after writes and is best effort. Existing tests cover imports,
manifest equivalence, lookup/resolver variants, API-key variants, bulk setup and
generated contract tests. These behaviors are the baseline, not permission to weaken
contracts.

## SC01 — Pure artifact generation

Add `generate_files(spec, *, spec_toml) -> dict[Path, str]` in the scaffold module.
Paths are relative to a destination; the mapping represents all generated files and
can be inspected without creating directories. Preserve existing programmatic source
generators and template selection. No filesystem access, subprocess, discovery, network
or formatter belongs in generation.

Validate semantic spec errors for direct callers before indexing first capabilities
or backends. Report them through ScaffoldError with useful context. Valid raw spec text
is copied exactly into `weaver.spec.toml`, including its final-newline choice; other
generated text has a deterministic final newline. Do not mutate the caller's spec.
No new public dataclass or abstract factory is needed for a path-to-text mapping.

Acceptance: repeated generation gives identical mappings; all relative paths and expected
variant artifacts match the current package shape; generation works without a destination
and leaves the filesystem untouched; invalid specs fail with actionable diagnostics.

## SC02 — Single-pass rendering and target-language encoding

Replace sequential replacement with a single pass over placeholders in the original
template. Missing bindings raise ScaffoldError naming the token and artifact. Extra
context bindings remain allowed because templates share context. Replacement values
are literal: never rescan them, and never reject user text merely because it contains
`{{TOKEN}}`. Do not detect unresolved bindings by scanning final output.

Distinguish structural generated code/identifiers from user data. Python expression
positions use Python literals; prose inserted into Python strings/docstrings/comments
must remain valid and preserve its intended data without allowing new source statements.
TOML string positions use an encoder accepted by stdlib tomllib; generated arrays/tables
remain structural. Markdown prose stays prose: avoid universal Python/HTML escaping.
Command/code examples containing free text must use the appropriate quoting for their
target. Keep declared names validated by existing spec rules; do not silently sanitize
invalid identifiers or change capability IDs.

Acceptance: placeholder-looking input survives literally; missing bindings fail;
quotes, backslashes, Unicode, multiline text and delimiter sequences produce valid
Python/TOML and round-trip the relevant metadata. Exercise actual scaffold artifacts,
not only the renderer helper.

## SC03 — Complete validation before filesystem mutation

Add `validate_files(files)` for the complete mapping. Reject absolute paths, traversal,
duplicate/aliased targets and incompatible parent/child file paths. Validate all generated
Python using compile/AST without importing or executing it. Parse generated pyproject.toml
and copied spec with tomllib. Verify generated project/package/version and entry-point
metadata remain consistent with the supplied spec through generation tests.

Scaffold must finish generation, content validation and destination preflight before
mkdir, overwrite or formatting. Preflight rejects a destination that is a file and
generated targets whose parent/target is an incompatible filesystem object. Refuse
symlink traversal through destination/parents/targets rather than writing outside the
intended tree. Force permits regular generated-file overwrites, not directory conflicts
or symlink traversal. This is a local correctness guard, not protection against a
concurrent adversarial filesystem change.

Acceptance: malformed generated Python/TOML, missing bindings, invalid paths and a
conflict late in the target list leave existing destination contents untouched and do
not create a new destination. Check the same guarantee with force enabled.

## SC04 — Explicit write boundary and preserved facade

Add `write_files(files, dest, *, force=False, format_output=True) -> list[Path]`.
It validates and preflights before writing even when called directly.
Keep `scaffold(spec, dest, *, spec_toml, force=False, format_output=True)` and its
sorted returned destination paths as the compatibility facade over generate/write.

Keep refusal of every nonempty destination without force, even when only unrelated
files exist. With force, replace generated regular files and retain unrelated files.
Do not invent selective regeneration in this step. Correct generated contributor
instructions that imply force protects implemented backend files. Never regenerate
the repository's handwritten NCBI vocab during this refactor.

Use explicit UTF-8 for writes. Format only generated Python after successful writes,
with the existing optional/best-effort formatter behavior. Generation/validation/write
errors must not be mistaken for unavailable formatting.

Acceptance: existing scaffold and CLI callers work; force/empty destination/format off/
formatter absent behavior is covered. An injected write failure propagates clearly.
Document that prevalidation is guaranteed but the multi-file write is not transactional:
disk failure or interruption during writes can leave partial output. No rollback,
staging-directory swap or filesystem transaction is promised in A06.

## SC05 — Distribution and compatibility gates

Keep domain-specific generator logic in weaverkit; no core or biological backend API
change is required. Keep inline templates initially; move them only if demonstrably
helpful and then prove wheel/sdist resource inclusion. Add no templating dependency,
ORM or frontend build tooling. Preserve generated TODO stubs and live-test gating.

Acceptance: existing conformance/contract checks stay intact; lookup/resolver,
local/keyless API/optional-key/required-key/bulk variants compile and import.
Generated manifests retain parameters, consumes_any, set_outputs, groups/provenance
and backend filtering. Generated test baselines remain intentionally unfinished:
strict verification must continue rejecting TODOs, not silently certify fresh stubs.
Run toolkit tests, workspace tests and lint; build/check the toolkit wheel and sdist
and generate/import representative packages from a clean installed wheel. Do not
download biological datasets or make live API calls for generator-only changes.

## Completion and delivery

SC01–SC05 must have recorded evidence before A06 is marked verified. Patch-bump
weaverkit for the compatible public generator APIs/fixes and update uv.lock; retain
its core floor unless an actual new core API is introduced. Use local commits on
`refactor/persistence-foundations`; update #145/#146, without new per-step issues.
No push, merge, tag or publication is authorized by this specification.
