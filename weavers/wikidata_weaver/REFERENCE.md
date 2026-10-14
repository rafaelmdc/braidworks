# Wikidata source reference

Exact source outputs, coverage and implementation constraints. Start with
[the package overview](README.md) for setup and query entry points.

## Capabilities

| Capability | Input types | Output groups / expandable keys | Backends | Parameters |
|---|---|---|---|---|
| `resolve_taxon` | `organism.scientific_name` | `core`, `names` | `api` | `expected_rank` |
| `map_from_taxid` | `ncbi.taxon.id` | `core`, `names` | `api` | — |
| `describe_taxon` | `wikidata.qid` | `core`, `localized` | `api` | `language` |

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
import wikidata_weaver

factory = WeaverFactory()
wikidata_weaver.register(factory)        # makes "wikidata" buildable
```

## Source response and failure handling

SPARQL envelopes and bindings are validated before accumulation. Query/service HTTP 400/404 is an error, never evidence of taxon absence; it is not retried. Taxon absence is a valid empty bindings list. Query literals escape quotes, backslashes and control characters. Each chunk has at most four attempts within a 90-second elapsed budget (including request time and waits); Retry-After seconds/HTTP dates are honored when they fit, otherwise the chunk fails without retrying early. Errors retain the final reason. expected_rank remains a homonym disambiguator: it chooses a uniquely matching rank only among multiple items and does not reject a single item with another rank.

Expected HTTP, JSON-decoding and explicitly validated source-data failures are returned as failure values. Cancellation and unrelated programming exceptions propagate. Existing successful output keys are preserved; consumers should handle `ERROR` separately from biological absence. Unknown extra source fields are allowed.

Aliases are distinct and lexically sorted. Conflicting English article titles,
taxon ranks, or sitelink counts for the same QID produce an error containing all
observed alternatives, rather than choosing the first binding. Homonyms retain
the existing candidate/review behavior.

## Construction and resource lifetime
For validated builders and client ownership, see
[shared configuration](../../docs/weaver-configuration.md).


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
