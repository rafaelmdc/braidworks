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
