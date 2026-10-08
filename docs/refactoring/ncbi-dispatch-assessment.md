# A08: NCBI dispatch fit assessment

Date: 2026-10-08. Requirement: AP08 / W13. Decision: **retain the source-local
runtime; do not introduce an adapter in this programme**. This is the specified
conditional rejection, not an unimplemented required refactor. Tracking: #145, #146.

## Capability comparison

The assessed package is `weavers/ncbi_weaver`, not domain-neutral core. The source
runtime is [dispatch.py](../../weavers/ncbi_weaver/src/ncbi_weaver/dispatch.py);
[core dispatch](../../braidworks-core/src/braidworks/core/dispatch.py) expects a
backend `fetch` operation and a shared mapper selected by the weaver class.

| Capability | Current backend operation | Mapping and controls | Fit with shared dispatch |
|---|---|---|---|
| `ncbi.resolve_name` | `resolve`, local/API | TaxonMatch; lineage gate; fuzzy/ambiguous candidates, review and warnings | Keep taxonomy mapper; generic resolver conversion changes candidate projection and loses warnings |
| `ncbi.describe_taxon` | `resolve`, local/API | TaxonMatch; core/lineage/species outputs; taxonomy score/lineage normalization | Typed normalization remains source-local; generic fetch/record bridge adds another representation |
| `ncbi.list_children` | `list_children`, API | Existing core LookupRecord/map_lookup; rank parameter; full taxon-ID set | Record mapping already shared; fetch adapter would forward the rank-specific source method |
| `ncbi.list_genomes` | `list_genomes`, API | Existing core LookupRecord/map_lookup; reference/annotation/assembly filters; accession set | Record mapping already shared; fetch adapter would forward three filters |
| `ncbi.describe_genome` | `describe_genome`, API | Existing core LookupRecord/map_lookup; assembly/sequences group gating | Record mapping already shared; fetch adapter must preserve group-controlled extra endpoint |
| `ncbi.resolve_gene` | `resolve_gene`, API | Existing core LookupRecord/map_lookup; taxon parameter, default 9606 | Despite its name, this is the existing lookup-record path; preserve that contract |
| `ncbi.describe_gene` | `describe_gene`, API | Existing core LookupRecord/map_lookup; summary/products group gating | Record mapping already shared; fetch adapter must preserve group-controlled extra endpoint |
| `ncbi.list_orthologs` | `list_orthologs`, API | Existing core LookupRecord/map_lookup; taxon filter; full gene-ID set | Record mapping already shared; fetch adapter would forward the source filter |

All eight retain source backend batching and request pacing. Set-output expansion,
review decisions, executor validation and caching remain core-owned. Six capabilities
already reuse the core record mapper; this is not eight independent mapping engines.

## Observed compatibility differences

The local probe `.audit-local/a08-fit-probe.py` constructs the same ambiguous taxon
candidate and requests lineage only. The current NCBI mapper retains taxon ID, name and
rank on the candidate (**three identifying strands**); core `map_resolver` filters those
candidate values against requested output groups (**zero identifying strands**). This
matters when a human selects a candidate for a downstream continuation.

NCBI TaxonMatch carries warnings; core ResolverRecord/map_resolver has no warning
carrier. The probe confirms the current warning survives and a generic conversion loses
it. Both score normalization and status mapping are similar, but those similarities do
not establish full result equivalence. NCBI also derives species IDs and serializes typed
lineage close to its source; those operations should remain in this package.

Generic dispatch resolves parameters for every capability. The current taxonomy path
ignores direct-call parameters, while the six lookup operations validate/default them.
The probe confirms an undeclared taxonomy parameter would be rejected by generic dispatch.
The generic runtime additionally checks returned batch length at dispatch time; the
current source runtime relies on the executor's contract validation. These are boundary
changes to account for, not assumptions of drop-in equivalence. This assessment does
not change either behavior or weaken executor validation.

## Alternatives and decision

A source-local adapter could technically preserve behavior: forward source identity and
pacing, implement fetch for all eight operations, retain TaxonMatch, and select the custom
or lookup mapper. It would still require the six source-method/parameter/group branches
and a mixed-mapper seam. It therefore moves the source dispatch into another wrapper
instead of eliminating its source decisions. Splitting lookup and taxonomy paths into
two internal weavers adds registry/identity composition for one public manifest.

Shared selection, fingerprint guards and single-to-batch bridging are small duplication.
Removing those alone by subclassing shared dispatch while overriding its main execution
method leaves an inherited mapper/fetch contract that the subclass does not actually use.
That is a poor trade for a few helper methods.

Retain the custom runtime and its supported thin-contract escape hatch. Do not widen
core resolver records solely to make this adaptation work, or change review candidate
projection as incidental cleanup. Reconsider when another mixed-record source needs the
same mechanism, or a separately specified taxonomy API change establishes full parity.
No adapter, biological backend, manifest, handwritten vocab or package version changes
are made by A08.

## Validation and acceptance

- Existing NCBI suite: **126 passed, 11 skipped**, covering direct/routed execution,
  local/API normalization, parameters, groups, review, set fan-out and bulk batching.
- The local mapper/parameter probe reproduced the differences above without network
  access or source data downloads; output: `.audit-local/a08-fit-probe.log`.
- Source implementations and handwritten vocabulary are unchanged. Live E2E is not
  required for this assessment-only decision; skipped live tests are not live assurance.

AP08/W13 acceptance is satisfied by this documented rejection with capability evidence.
Final programme gates and remote delivery are tracked separately.
