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
