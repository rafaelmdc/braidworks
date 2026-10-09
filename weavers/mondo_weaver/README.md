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
mondo_weaver.register(factory)        # makes "mondo" buildable
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
