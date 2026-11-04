# PDBe source group #159

#195 completed: spec comments now describe observed bulk POST best_structures
chunks of 100 (singleton GET), summary POST chunks of 200 and keyed correlation.
README qualifies deterministic ordering by the same observed live response, not
unchanging remote content. Contributor notes describe full fan-set/display limits,
chain evidence and separate costs/scopes for future quality/assembly/ligand services.
A complete configured Python example runs live successfully; package tests and
strict conformance/goldens pass. Documentation-only: no runtime/version change.

#193 remains a feature scope decision: existing structure records already retain
chain/source/range evidence from SH-08. Additional normalized chain/range outputs
and quality data require a field/group/request-cost decision; assembly/ligand
services are separate proposed workflows, not implemented here.

## Approved span and quality scope — #193

Version 0.1.13 projects observed mapping spans without claiming full residue
alignment or author numbering. Ranking, multi-chain evidence and fan/display
limits remain unchanged. A requested quality group uses one chunked POST for
entry IDs and preserves provider metrics, missing values and experimental method.
Default detail queries make no quality request.

Observed live POST `/validation/summary_quality_scores/entry` returned keyed
objects for both 1tup and 4hhb; the source sample includes its real 1tup response.
[PDBe quality documentation](https://www.ebi.ac.uk/training/online/courses/exploring-pdb-entry/pdb-entry-overview/model-quality/)
provides interpretation context. Assemblies, ligands and full residue alignment
remain deferred; this minimum scope does not close all of #193.

Verification: 63 package tests passed, six opt-in skips; strict verification and
six live checks passed. Added regressions cover disjoint chain spans, bulk
quality requests, unchanged default request count and missing metric semantics.
