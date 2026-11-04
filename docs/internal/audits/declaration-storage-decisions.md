# Declaration and key-storage decisions — #112 and #64

Reviewed 2026-10-15. Both issues contain a title only, with no comments, examples or
acceptance criteria. The review therefore evaluates the current contribution workflow
rather than assuming a missing runtime database or decorator API is required.

## #112 — Strand decorators: not planned

A strand is a data value: `Strand(type_id, value, confidence, provenance, metadata)`.
It already normalizes registered keys and round-trips through JSON. A decorator would
need to decorate a function or class, so it would introduce another declaration concept
rather than simplify construction of a value.

If the intended goal is defining new source outputs, the existing contract is the
weaver TOML spec: outputs live in groups alongside consumed keys, backend support,
parameters, provenance and golden examples. Scaffolding generates capabilities and
mapping; shared mappers construct strands with execution provenance. A parallel
function-decorator declaration would need to reproduce or synchronize that contract,
including grouped outputs and batches. A decorator could carry explicit metadata
without global registration, but there is no concrete repeated workflow demonstrating
its benefit here. An implementation using import-time registration would also make
available vocabulary depend on which modules happened to load.

Decision: retain plain strand values and spec-driven capability declarations. No public
decorator or registration side effects are added. Reopen with a concrete before/after
example if repeated adapter boilerplate cannot be expressed through the scaffold,
records and shared mapper. That evidence can establish whether a small pure helper or
a deliberate decorator API actually removes work without hiding execution semantics.

Evidence: `core/strand.py`, `core/mapper.py`, `weaverkit/spec.py`, scaffold-generated
vocab and the runtime/conformance tests. These are existing implementation choices,
not a claim that decorators are universally inappropriate.

## #64 — Key database: not planned

The current vocabulary contains 41 shared keys and 156 leaf/output keys. Toolkit
registries provide descriptions/reachability checks; core canonical types normalize
runtime bridge values. There are 40 canonical entries; entry keys can deliberately be
exempt. Toolkit parity tests verify that distinction. Generated indexes and capability
inventories provide searchable source/input/output views without a second writable store.

The catalogue is distributed as versioned package code. Changes are deliberate diffs
reviewed alongside producers/consumers and tests. There is no current requirement for
concurrent catalogue writes, user-created persistent vocabulary, server-side queries or
independent vocabulary releases. Moving it into SQLite would still require a shipped
canonical dataset, distribution/version rules and synchronization with runtime types;
it would add schema/file access responsibilities without removing the semantic review.
A mutable machine-local catalogue would additionally let identical package versions
validate or normalize inputs differently across machines.

Decision: keep the versioned source catalogue and generated views. Do not conflate it
with the existing SQLite result cache/run database or multi-GB biological source data.
Reopen when an actual independently managed catalogue service or persistent user-defined
vocabulary has defined ownership, versioning and query requirements. If maintenance
work grows first, consolidating metadata into a reviewed static source could be assessed
without committing to mutable database infrastructure.

Evidence: `weaverkit/keys.py`, `core/keytypes.py`, `weaverkit/index.py`, spec validation
and `weaverkit/tests/test_conformance.py`'s canonical/shared-key parity checks. Existing
core/toolkit suites cover canonical normalization, registration and serialization.

## Resolution and verification

Close both issues as **not planned**, rather than completed implementations. The current
loop adds no storage/decorator API for them. No runtime code, package versions or existing
conformance checks change in this decision. The author can reopen either issue with the
missing workflow context. Vocabulary counts were read from the installed editable source;
core/toolkit checks and generated-inventory checks pass. Documentation links and whitespace
are checked before committing.
