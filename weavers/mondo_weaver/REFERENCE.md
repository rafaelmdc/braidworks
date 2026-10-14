# MONDO source reference

Exact source outputs, coverage and implementation constraints. Start with
[the package overview](README.md) for setup and query entry points.

## Capabilities and output groups

| Capability | Input types | Output groups / expandable keys | Backends | Parameters |
|---|---|---|---|---|
| `mondo.lookup_by_mesh` | `disease.mesh.id` | `identity`, `term`, `ancestors` | `local` | — |
| `mondo.lookup_by_meddra` | `disease.meddra.id` | `identity`, `term`, `ancestors` | `local` | — |
| `mondo.lookup_by_name` | `disease.name` | `identity`, `term`, `ancestors` | `local` | — |
| `describe_disease` | `disease.mondo.id` | `identity`, `definition`, `history`, `term`, `ancestors`, `mappings` | `local` | — |

These are the current declared capabilities. Output groups select fields computed
together; expandable keys identify related entities you can follow. See
[the spec](weaver.spec.toml) for exact output fields and parameter defaults, or
`braidworks weavers` for the installed inventory. Backend declarations do not imply
that optional local data are already configured.

## Registering this weaver

The CLI discovers this installed weaver through its entry point. Python applications
can register a built instance directly in `BraidRegistry`. `WeaverFactory` registration
is optional construction support; it makes the builder available by ID, not a route.
For applications using that factory:

```python
from braidworks.core import WeaverFactory
import mondo_weaver

factory = WeaverFactory()
mondo_weaver.register(factory)  # makes "mondo" buildable
```

## Source provenance and ontology validation

The current schema retains the original OBO SHA-256, observed `data-version`, source descriptor
and acquisition time. A missing/unknown release is represented as an explicitly
unversioned content hash, rather than a fabricated release. Caller-supplied terms
have a separately labelled normalized-content hash and do not claim an OBO byte hash.
The existing `SourceBinding` ties metadata and lookups to the same local generation.

`ensure_mondo_db(..., expected_version="releases/YYYY-MM-DD")` and the configured
builder accept an expected OBO header version. A mismatch fails the staged build;
it does not relabel a different release. This is a version check, not an archive
selection API: the default download still acquires the current provider OBO.

Builders and validators check unique term identifiers, names, parent references,
acyclic `is_a` edges, referential coherence of name/xref tables and recorded counts.
Invalid graphs are rejected before writing. Schema 1 databases require rebuilding
to obtain source provenance and the stronger validation gate.

### Identity and mapping evidence

The current schema retains mapping relationships and original xref text, including equivalent,
MONDO-broader/narrower, related, sibling, SKOS exact/close/broad/narrow and unspecified
relationships. `disease.ontology.mapping.records` exposes observed evidence. Only a
unique explicit `MONDO:equivalentTo` supplies confident cross-reference identity.
Other relations, including SKOS exact match, require review; they are preserved in
the error evidence without silently becoming equivalence. Ambiguous names or
multiple equivalent IDs also require review. Rebuild schema-2 databases.

The distinction follows the provider's
[mapping semantics](https://mondo.monarchinitiative.org/pages/faq/) and
[quality-control relation codes](https://mondo.readthedocs.io/en/latest/editors-guide/quality-control-tests/).

## Group-aware graph reads

The always-computed `identity` group now contains MONDO ID, name and mapping
evidence. `term` contains parents and depth; `ancestors` remains separate.
Requests for identity alone do not traverse the graph. When graph fields are
requested, one traversal supplies names, direct parents and shortest root depth,
reused for the same resolved term within a batch. Result projections are detached.

Migration: clients selecting groups explicitly should include `identity` for
identity fields previously in `term`. Output-key requests need no change. This
group separation originally used schema 3 without a rebuild. Current releases
require schema 5 for obsolete-term and optional SSSOM support; rebuild older databases.

## Coverage measurement

No fixed resolution percentage is promised. Measure a declared source ID/name
cohort against a recorded MONDO data version, report the denominator, unique
equivalent matches, ambiguous/non-equivalent review cases and misses separately.
Name lookup uses normalized exact labels/synonyms; it does not establish that a
clinical term is equivalent just because a label matches.

## Construction and resource lifetime
For validated builders and client ownership, see
[shared configuration](../../docs/weaver-configuration.md).


## Synthetic fixture example

```python
import asyncio
from braidworks.core import Strand, StrandSet
from mondo_weaver.factory import build_mondo_weaver_fixture


async def main():
    async with build_mondo_weaver_fixture() as weaver:
        result = (
            await weaver.execute_batch(
                "mondo.lookup_by_mesh",
                [StrandSet.from_strands("example", [Strand("disease.mesh.id", "D003093")])],
                requested_outputs=frozenset({"disease.mondo.id"}),
                backend="local",
            )
        )[0]
        print(result.to_json())
        result = (
            await weaver.execute_batch(
                "mondo.lookup_by_meddra",
                [StrandSet.from_strands("example", [Strand("disease.meddra.id", "10045365")])],
                requested_outputs=frozenset({"disease.mondo.id"}),
                backend="local",
            )
        )[0]
        print(result.to_json())
        result = (
            await weaver.execute_batch(
                "mondo.lookup_by_name",
                [StrandSet.from_strands("example", [Strand("disease.name", "ulcerative colitis")])],
                requested_outputs=frozenset({"disease.ontology.ancestors"}),
                backend="local",
            )
        )[0]
        print(result.to_json())


asyncio.run(main())
```

### Source validation

Malformed cyclic or dangling ancestry data returns an error rather than a partial match. Valid DAGs retain shortest ancestor depths.

`describe_disease` consumes `disease.mondo.id` directly, including obsolete IDs.
Requested definition/history groups report observed definitions, obsoletion,
`replaced_by` and `consider` targets with release/source identity. Consider targets
remain suggestions; the weaver never follows them as automatic replacements.
Obsolete terms stay out of name and equivalence resolution indexes.

The current database is schema 5; rebuild older local databases. Obsolete-term
retention and existing name/xref relation review are preserved. Release-matched
SSSOM ingestion is implemented as an optional input, described below; it does not
reinterpret all cross-references as equivalence.
Source: [MONDO obsoletion guidance](https://mondo.readthedocs.io/en/stable/editors-guide/merging-and-obsoleting/).

### Typed external mappings

`describe_disease` can return `disease.ontology.external_mappings` when requested.
Build with `mapping_path="mondo.sssom.tsv"` and
`mapping_release="2026-10-06"` alongside `expected_version="releases/2026-10-06"`.
Use the canonical SSSOM file from the **same tagged MONDO release** as the OBO:
[observed tagged source](https://github.com/monarch-initiative/mondo/blob/v2026-10-06/src/ontology/mappings/mondo.sssom.tsv).
The release is supplied explicitly because this file's metadata has no release date;
the caller must acquire it from that tag. Ingestion rejects mismatched dates and
subjects absent from the ontology. Every row retains its directional predicate,
justification and extra columns; metadata and the mapping byte hash accompany results.
Broad, narrow, related and exact mappings remain distinct. This optional dataset does
not change existing OBO-based identity resolution.

Schema 5 rebuilds older databases. Supplying a changed mapping file invalidates reuse;
source fingerprints include its hash. Without ingestion, requesting mappings returns
an actionable error instead of implying that an empty list means no mappings exist.
No SSSOM download occurs implicitly; ordinary OBO acquisition retains its consent gate.
