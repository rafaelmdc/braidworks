# mondo_weaver

MONDO disease ontology (MeSH/MedDRA disease id -> unified MONDO id + is-a ancestors) weaver for Braidworks.

- **Source:** https://mondo.monarchinitiative.org
- **License:** CC-BY-4.0
- **Cite:** https://doi.org/10.1101/2022.04.13.22273750

## Setup and use

The implemented local backend reads a SQLite index built from the MONDO OBO
ontology. Prepare the default cache explicitly; this downloads the source file:

    from mondo_weaver.setup import ensure_mondo_db
    ensure_mondo_db(auto=True)

Then query a source identifier from the installed CLI:

    braidworks run mondo mondo.lookup_by_mesh --have disease.mesh.id=D003093

For an existing database at a custom location:

    from mondo_weaver.factory import build_mondo_weaver_configured
    weaver = build_mondo_weaver_configured(db_path="/path/to/mondo.sqlite")

Separate capabilities accept MeSH IDs, MedDRA IDs and disease names. Consult the
spec or braidworks weavers for their exact output groups. The lookup represents
ontology cross-references; it does not perform clinical diagnosis. Offline fixture
and golden tests are already implemented.

```bash
make verify   # check the weaver still matches its spec
make test     # run conformance + contract + golden tests
```

## Registering this weaver

A weaver is only reachable to the braider once its provider is registered in the
application's `WeaverFactory`. Wherever you assemble the factory:

```python
from braidworks.core import WeaverFactory
import mondo_weaver

factory = WeaverFactory()
mondo_weaver.register(factory)  # makes "mondo" buildable
```

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/weavers/mondo_weaver/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.

## Source provenance and ontology validation

Schema 2 records the original OBO SHA-256, observed `data-version`, source descriptor
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

Schema 3 retains mapping relationships and original xref text, including equivalent,
MONDO-broader/narrower, related, sibling, SKOS exact/close/broad/narrow and unspecified
relationships. `disease.ontology.mapping.records` exposes observed evidence. Only a
unique explicit `MONDO:equivalentTo` supplies confident cross-reference identity.
Other relations, including SKOS exact match, require review; they are preserved in
the error evidence without silently becoming equivalence. Ambiguous names or
multiple equivalent IDs also require review. Rebuild schema-2 databases.

The distinction follows the provider's
[mapping semantics](https://mondo.monarchinitiative.org/pages/faq/) and
[quality-control relation codes](https://mondo.readthedocs.io/en/latest/editors-guide/quality-control-tests/).

## Group-aware graph reads (0.2.5)

The always-computed `identity` group now contains MONDO ID, name and mapping
evidence. `term` contains parents and depth; `ancestors` remains separate.
Requests for identity alone do not traverse the graph. When graph fields are
requested, one traversal supplies names, direct parents and shortest root depth,
reused for the same resolved term within a batch. Result projections are detached.

Migration: clients selecting groups explicitly should include `identity` for
identity fields previously in `term`. Output-key requests need no change. This
change uses the existing schema-3 database and does not require rebuilding it.

## Coverage measurement

No fixed resolution percentage is promised. Measure a declared source ID/name
cohort against a recorded MONDO data version, report the denominator, unique
equivalent matches, ambiguous/non-equivalent review cases and misses separately.
Name lookup uses normalized exact labels/synonyms; it does not establish that a
clinical term is equivalent just because a label matches.

## Construction and resource lifetime

Supported builder options are explicit; unknown options raise
`BackendConfigurationError`. Empty construction remains safe for discovery.
See [configuration and lifetime](../../docs/weaver-configuration.md) for provider
configuration, source selection and owned/borrowed HTTP clients. Use
`async with weaver:` or `await weaver.aclose()` after requests finish.

## Capabilities and output groups

| Capability | Input | Outputs by group |
|---|---|---|
| `mondo.lookup_by_mesh` | `disease.mesh.id` | **identity**: `disease.mondo.id`, `disease.ontology.mapping.records`, `disease.ontology.name`; **term**: `disease.ontology.depth`, `disease.ontology.parents`; **ancestors**: `disease.ontology.ancestors` |
| `mondo.lookup_by_meddra` | `disease.meddra.id` | **identity**: `disease.mondo.id`, `disease.ontology.mapping.records`, `disease.ontology.name`; **term**: `disease.ontology.depth`, `disease.ontology.parents`; **ancestors**: `disease.ontology.ancestors` |
| `mondo.lookup_by_name` | `disease.name` | **identity**: `disease.mondo.id`, `disease.ontology.mapping.records`, `disease.ontology.name`; **term**: `disease.ontology.depth`, `disease.ontology.parents`; **ancestors**: `disease.ontology.ancestors` |

## Complete offline Python example

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

Schema 4 retains obsolete terms and requires rebuilding older local databases.
Existing name/xref ambiguity and relation review are preserved. Release-matched
SSSOM mapping ingestion remains a separate deferred feature; this change does
not reinterpret all cross-references as equivalence.
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
