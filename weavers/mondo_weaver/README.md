# mondo_weaver

Resolve disease names or MeSH/MedDRA identifiers to MONDO and inspect ontology terms, ancestors
and mapping evidence. Queries use a prepared local OBO index; typed mappings additionally
require release-matched SSSOM data. Mapping relations have different meanings and do not
establish clinical equivalence or diagnosis.

- **Source:** https://mondo.monarchinitiative.org
- **License:** CC-BY-4.0
- **Cite:** https://doi.org/10.1101/2022.04.13.22273750

## Capabilities

| Capability | Use it to |
|---|---|
| `mondo.lookup_by_mesh` | Resolve a MeSH identifier through observed mappings |
| `mondo.lookup_by_meddra` | Resolve a MedDRA identifier through observed mappings |
| `mondo.lookup_by_name` | Resolve an exact normalized label or synonym |
| `describe_disease` | Inspect an exact MONDO identity |

See [source reference](REFERENCE.md#capabilities-and-output-groups) for exact inputs, output groups, backends and parameters,
or inspect the [spec](weaver.spec.toml).

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

## Setup, interpretation and contribution

Use [checkout or wheel installation](../../docs/installation.md) with core and the
sources needed for your route. From the checkout, prefix commands above with
`uv run --no-sync`; a bare command assumes the environment is activated.
Source installation does not acquire optional biological databases.

[Source reference](REFERENCE.md) retains coverage, selection, failure and resource
rules. [Builder configuration](../../docs/weaver-configuration.md) documents supported
options and ownership; close configured weavers after work completes. See
[contributing](CONTRIBUTING.md) to extend this source, and run package checks from
this package directory. Current installation does not assume package-index publication.

## Software license

The software uses [MIT](LICENSE). Provider data retain their source licenses and
attribution requirements above; the manifest data license does not license this code.
