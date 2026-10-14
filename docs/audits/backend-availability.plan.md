# Backend availability diagnostics — implementation plan

Implements [the focused specification](backend-availability.spec.md) for
[issue #132](https://github.com/rafaelmdc/braidworks/issues/132).
Status: planned; audit/reproduction complete, runtime implementation pending.
Branch: `feat/backend-availability-diagnostics`.

## P1 — Declaration contract and registration

Add the backward-compatible declaration hook with a default of the active manifest.
Define catalogue/active consistency for IDs, versions, capability inputs/outputs/groups/
parameters and backend subsets. Validate both through existing rules. Store declared
metadata separately; keep active `manifests()` and `build_graph()` behavior unchanged.

Tests: legacy adapter fallback, full/narrow declarations, invalid mismatches, unchanged
active graph. Reuse `WeaverManifest` serialization; do not add a new public dataclass.

## P2 — Diagnostic lookup and planner failures

Create a small helper for known/inactive/unknown capability lookup and deterministic
backend context. Add a diagnostic projection for failed routes using declared metadata.
Use it only after ordinary routing fails. Preserve policy, exclusion and graph-shape
rules. Name blockers on a connecting route rather than listing unrelated capabilities.
Keep unreachable paths as `NoPathError`; configuration/policy blockers use `NoPlanError`.
Apply the same lookup to explicit-capability planning.

Tests: direct and multihop blockers, policy-only blocks, alternatives, unknown targets,
disconnected inputs, excluded edges, conjunctions, already-satisfied targets and legacy
adapters. Verify that successful plans retain the same invocation/backend assignments.

## P3 — Source declaration adoption and dispatch preflight

Expose NCBI's full declaration without constructing API/local backends. Keep its active
manifest filtering. Shared and handwritten dispatch check capability/backend support
before pacing/source calls, with the established exception distinctions.

Tests: local-only NCBI descendant planning succeeds; API-only gene/genome operations
receive disabled-backend context. Unknown capability remains unknown. Incompatible backend
selection performs no fetch/resolve. Declared-but-unconfigured fallback remains unchanged.
Use inert adapters and tiny fixtures, not live NCBI or acquired databases.

## P4 — CLI/browser and scaffold integration

Make direct CLI lookup use the same declaration-aware context. Browser planning already
catches both planning exception classes; verify its reported message and failure status.
Preserve ordinary discovery inventories and persistence/source identity payloads.

Generate the full declaration hook in new scaffolds from spec backends. Test subset
construction and strict verification without weakening conformance. Existing sources
that do not discard declarations can retain the default hook; extend adoption only where
inspection establishes a need. Do not force-regenerate implemented source packages.

## P5 — Documentation and package versions

Document the declaration hook and the distinction between support, enabled backends and
runtime configuration in core contracts/backend reference. Update source configuration
advice and record that the issue's original descendant case was already fixed.

Bump core for the additive public API and changed diagnostic behavior. Bump toolkit for
changed scaffold output, and NCBI for its declaration/dispatch behavior. Raise the required
core floors for packages using the new hook/helper. Synchronize NCBI's three version
sites; its handwritten vocab may be edited deliberately. Leave other source manifests
and generated vocab alone unless their behavior changes. Do not create tags manually.

## P6 — Acceptance and delivery

Rerun the isolated reproduction and record before/after distinctions. Run affected core,
NCBI and toolkit suites, then workspace lint/test through the Makefiles with the existing
isolated environment. No API backend fetch code is planned; if implementation expands to
it, apply AGENTS' live-E2E requirement. Verify docs links and whitespace.

Review persistence/archive compatibility and unchanged successful routing. Commit reviewable
increments on the feature branch. Keep #132 open until acceptance passes; then update/close
it with evidence under the established issue workflow. Do not close #131/#133 or deferred
work as a side effect. Push only when this implementation is ready for delivery.

## Guard against scope growth

Do not add readiness-aware routing, global backend probes, automatic enabling/downloads,
source-specific configuration hints in core, mandatory catalogue adoption for legacy plugins,
or a broad error-system redesign. If validation exposes a separate runtime bug, record
its evidence and decide its scope before folding it into this implementation.
