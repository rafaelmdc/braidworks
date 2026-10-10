# wikidata_weaver

Wikidata taxon names (scientific name -> QID, vernacular names, enwiki title) weaver for Braidworks.

- **Source:** https://www.wikidata.org/
- **License:** CC0-1.0
- **Cite:** Wikidata, the free knowledge base. https://www.wikidata.org/

## Use it

The implemented keyless SPARQL backend resolves taxon scientific names to Wikidata
items, English Wikipedia titles, sitelink counts and vernacular names.

    braidworks run wikidata resolve_taxon --have organism.scientific_name="Ursus arctos"

Names shared across taxonomic codes can have several candidates. Routed execution
pauses on ambiguity by default. If the expected rank is known, refine the query:

    braidworks weave --have organism.scientific_name="Ursus arctos" --want wikidata.qid --param expected_rank=species

From Python, build_wikidata_weaver() needs no configuration. Offline fixture and
golden tests are implemented; live use depends on the public SPARQL endpoint.

```bash
make verify   # check the weaver still matches its spec
make test     # run conformance + contract + golden tests
```

## Registering this weaver

A weaver is only reachable to the braider once its provider is registered in the
application's `WeaverFactory`. Wherever you assemble the factory:

```python
from braidworks.core import WeaverFactory
import wikidata_weaver

factory = WeaverFactory()
wikidata_weaver.register(factory)        # makes "wikidata" buildable
```

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/weavers/wikidata_weaver/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.


## Source response and failure handling

SPARQL envelopes and bindings are validated before accumulation. Query/service HTTP 400/404 is an error, never evidence of taxon absence; it is not retried. Taxon absence is a valid empty bindings list. Query literals escape quotes, backslashes and control characters. Each chunk has at most four attempts within a 90-second elapsed budget (including request time and waits); Retry-After seconds/HTTP dates are honored when they fit, otherwise the chunk fails without retrying early. Errors retain the final reason. expected_rank remains a homonym disambiguator: it chooses a uniquely matching rank only among multiple items and does not reject a single item with another rank.

Expected HTTP, JSON-decoding and explicitly validated source-data failures are returned as failure values. Cancellation and unrelated programming exceptions propagate. Existing successful output keys are preserved; consumers should handle `ERROR` separately from biological absence. Unknown extra source fields are allowed.

Aliases are distinct and lexically sorted. Conflicting English article titles,
taxon ranks, or sitelink counts for the same QID produce an error containing all
observed alternatives, rather than choosing the first binding. Homonyms retain
the existing candidate/review behavior.

## Construction and resource lifetime

Supported builder options are explicit; unknown options raise
`BackendConfigurationError`. Empty construction remains safe for discovery.
See [configuration and lifetime](../../docs/weaver-configuration.md) for provider
configuration, source selection and owned/borrowed HTTP clients. Use
`async with weaver:` or `await weaver.aclose()` after requests finish.

Stable identity entry points: `map_from_taxid` consumes `ncbi.taxon.id` and
resolves the observed P685 mapping through bulk SPARQL; duplicate items remain
ambiguous/reviewable instead of picking one. `describe_taxon` consumes a QID
and uses bulk `wbgetentities` (50 IDs), with explicit missing and redirect
identity. It describes items with observed scientific-name claims.

Use `--param language=pt` with the requested `wikidata.localized` group to obtain
a label/description in Portuguese, falling back to English when absent. Requested
and actual label/description languages are recorded separately. `wikipedia.title`
continues to come exclusively from `enwiki`, so it remains compatible with the
English Wikipedia weaver. The entity API requests all sitelinks before counting
them; a filtered English-only response is never passed off as the total.

Builders accept `entity_api_url` separately from the SPARQL `base_url`; both
source settings contribute to the backend fingerprint. Existing name/rank
resolution is unchanged. Sources: [Wikibase API](https://www.mediawiki.org/wiki/Wikibase/API),
[language-aware presentation](https://www.mediawiki.org/wiki/API:Presenting_Wikidata_knowledge).
