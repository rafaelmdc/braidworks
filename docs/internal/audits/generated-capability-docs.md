# Generated capability documentation — #67

## Scope and implementation

The docs reorganization moved exact capability inventories into source references,
but their generation remained missing. Add one deterministic renderer from WeaverSpec,
explicit start/end markers, a workspace/package command and a non-mutating CI check.
New scaffolds use the same renderer. Leave purpose/usage tables, source semantics and
implementation limitations under human ownership. No new documentation dependency or
runtime provider calls are needed.

The updater validates all specs and marker ownership before writing any changes.
It reports stale paths in check mode. One-time migration marks only existing exact
inventories: 16 source references and the teaching README. Generation normalizes
AGORA and UniProt input ordering to match their specs.
Tests cover repeated updates, prose preservation, alternatives, per-capability backend
selection, scaffold parity, malformed markers and no partial writes on invalid input.

## Acceptance

Implemented 2026-10-15. Workspace lint, 305 toolkit tests and the workspace drift check
passed. All 17 marked tables match their specs. Documentation validation checked 1,292
links/anchors in 244 documents, and whitespace passed. Capability semantics, runtime
routing and human source explanations are unchanged. The command does not import source
providers or acquire data. CI now rejects inventory drift.
