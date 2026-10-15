# AGORA source reference

Exact source outputs, coverage and implementation constraints. Start with
[the package overview](README.md) for setup and query entry points.

## Capabilities

| Capability | Input types | Output groups / expandable keys | Backends | Parameters |
|---|---|---|---|---|
| `describe_metabolic_reconstruction` | `ncbi.taxon.id` | `core`, `reactions`, `model` | `local` | — |
| `list_reconstructions` | `genome.accession` or `ncbi.taxon.id` | `reconstructions`; expands `microbe.agora.reconstruction_id` | `local` | — |
| `describe_reconstruction` | `microbe.agora.reconstruction_id` | `identity`, `artifact`, `reactions`, `model` | `local` | — |
| `list_genomes` | `microbe.agora.reconstruction_id` | `genomes`; expands `genome.accession` | `local` | — |
| `list_reactions` | `microbe.agora.reconstruction_id` | `reactions`; expands `reaction.vmh.id` | `local` | — |
| `describe_reaction` | `reaction.vmh.id` | `reaction` | `local` | — |

These are the current declared capabilities. Output groups select fields computed
together; expandable keys identify related entities you can follow. See
[the spec](weaver.spec.toml) for exact output fields and parameter defaults, or
`braidworks weavers` for the installed inventory. Backend declarations do not imply
that optional local data are already configured.

## Outputs (grouped)

- **`core`** → `microbe.metabolism.reconstruction`: a list of `{reconstruction_id, gcf_id}`
  (the AGORA2 model and the RefSeq genome it was built from). Served from a **bundled**
  crosswalk (AGORA2 Supplementary Table S1) — **offline, all 7,302 strains, no download.**
- **`reactions`** → `microbe.metabolism.reactions`: the per-model reaction repertoire, a
  list of `{reconstruction_id, abbreviation, subsystem, ec, kegg, rhea}` (EC/KEGG/Rhea from
  the VMH reaction crosswalk — so this also acts as an **intermediate** into the molecular
  hub). Needs the reaction DB built by `ensure_agora_db` from the AGORA2 SBML archive
  (~2.17 GB, consent-gated); absent it, `core` still answers.

- **`model`** → `microbe.metabolism.sbml`: reconstruction ID, cached SBML path
  and source URL per model. Use `sbml_cache_dir` and explicitly enable
  `auto_download_models` to permit missing-model acquisition. Requested uncached
  models without consent are errors; they are not silently omitted.

```python
import agora_weaver

# core only (offline, no download):
weaver = agora_weaver.build_agora_weaver()

# also build the reaction repertoire DB (downloads the 2.17 GB SBML archive):
weaver = agora_weaver.build_agora_weaver(auto_setup=True)
```

```bash
make verify   # check the weaver still matches its spec
make test     # conformance + contract + golden tests (offline)
```

## Registering this weaver

The CLI discovers this installed weaver through its entry point. Python applications
can register a built instance directly in `BraidRegistry`. `WeaverFactory` registration
is optional construction support; it makes the builder available by ID, not a route.
For applications using that factory:

```python
from braidworks.core import WeaverFactory
import agora_weaver

factory = WeaverFactory()
agora_weaver.register(factory)        # makes "agora" buildable
```

## Safe local database rebuilds

Direct builders and acquisition builds stage a fresh database beside the target,
validate its query schema and publish it atomically under the existing build lock.
Successful rebuilds remove rows from older datasets; failed input, validation or
publication leaves the original database unchanged. Allow space for both databases
and close writable target connections before replacement. Keep application-owned
tables in a separate database. Explicit local builds do not enforce the large
download disk margin used by consent-gated acquisition.

`build_reaction_db()` records the SBML content hash and the annotation row count,
SHA-256 and source. Optional `annotation_source=` and `sbml_source=` identify source
URLs; without them, metadata labels annotations caller-supplied and records the
local archive path. The annotation digest covers ordered JSON rows, not raw HTTP
bytes; it provides reproducibility evidence rather than a canonical dataset ID.
The XML parser releases processed elements, including nonreaction data.

## Resource and model coverage

Core-only crosswalk queries work offline. Requesting reactions without a reaction
database, or an unavailable SBML model without download consent, returns `ERROR`;
failed results claim no completed output groups. Partial SBML availability also
fails the requested model group rather than silently dropping reconstructions.

Reaction database schema 2 persists every processed/skipped XML model, its source
member, distinct reaction count and parse error. A processed model with zero
reactions is a known empty repertoire; a skipped or unacquired model is unavailable.
Existing databases without this manifest must be rebuilt before serving reactions.

## Bounded local work

The bundled crosswalk is retained as immutable tuples; public lookups return
detached dictionaries and lists. Reaction lookup deduplicates model IDs and uses
two SQL queries per chunk of at most 250 models. Processed empty models remain
valid empty repertoires; skipped or missing coverage remains an error.

The configured wrapper preserves `auto_setup=False`; its name does not grant
download consent. Existing databases can be supplied without enabling downloads.

## Construction and resource lifetime
For validated builders and client ownership, see
[shared configuration](../../docs/weaver-configuration.md).


## Individual model artifact safety

Cached and downloaded model files must parse completely as SBML with an identified
model. This is structural validation, not a full biochemical/schema check. Acquisition
uses a per-target process lock and staged atomic publication; malformed XML or HTML
responses cannot become valid cached models. Download consent remains required.

SBML records include local `path`, portable `source_url`, AGORA `release`, observed
`model_id` and content `sha256`. Use the URL and hash when transferring results to
another machine; the path only applies to this machine. Backend fingerprints include
model-cache directory, download policy and artifact stat identity, as well as reaction
source identity. Artifact acquisition/replacement changes that identity.

`CC-BY-NC-4.0` is now a recognized **restricted** source license; recognition does not
relax the noncommercial terms. References retain attribution and noncommercial notices.
The license meaning is described by [Creative Commons](https://creativecommons.org/licenses/by-nc/4.0/).

Live validation on 2026-10-10 verified VMH's current individual-model service:
`https://vmh.life/api/getMicrobeReconstructions?version=agora2_2.01&format=sbml&id=<reconstruction_id>`.
The explicit family selector pins AGORA2 version 2.01. This service generates SBML
from the provider's release data; it is not a byte-identical copy of the original
archive XML. The obsolete static route returned HTML and is no longer the default.
Caller-configured XML directories can be supplied through `model_download_base_url`;
that configuration affects backend fingerprints and exported source URLs.

`list_reconstructions` emits the full distinct `microbe.agora.reconstruction_id`
set (`AGORA2-v2.01:<model>`), a capped display of ten crosswalk records and coverage.
`describe_reconstruction` consumes that release-qualified key. Its identity group
retains exact source taxid/genome associations; reactions/model groups reuse the
existing resource and consent behavior. IDs for other releases are explicit errors.

The requested artifact group reports local structural validation, model ID/hash,
and availability. It never starts downloads. A cached file is **not** proof of
its AGORA release: `release_verified` remains false. Missing artifacts report
consent-required or not-cached according to effective consent.
Metadata describes service availability without fetching it; it does not claim
exhaustive model availability, archive-byte equivalence or a solver result.

### Genome and reaction bridges

`list_reconstructions` now also accepts exact `genome.accession`; an explicitly
supplied genome is authoritative if both alternatives occur. The pinned crosswalk
retains assembly versions and does not guess GCA/GCF equivalence or latest versions.
`list_genomes` consumes a release-qualified reconstruction ID and emits the full
observed assembly set, preserving exact model/strain associations.

`list_reactions` consumes that same model identity and uses the acquired reaction
DB to emit the full sorted `reaction.vmh.id` set plus ten display records and true
counts. `describe_reaction` consumes one VMH abbreviation and reports source
annotations and observed model memberships with database release/content identity.
Missing annotations remain null, not guessed KEGG/Rhea equivalence. Unprocessed
model coverage is an error, not an empty repertoire. These routes require no new
HTTP calls or model acquisition; missing reaction databases remain explicit errors.

## Exact taxid universe

`agora_weaver.crosswalk_taxids()` returns an immutable `frozenset[int]` of exact
NCBI taxids in the bundled reconstruction crosswalk. It uses the same index as
reconstruction lookup, performs no downloads and does not require a reaction DB.
The release identifier is `agora_weaver.dataset.CROSSWALK_RELEASE`.

This is reconstruction-crosswalk membership. It does not guarantee reactions or an
SBML artifact, and it does not expand genera, normalize strains to species, or infer
ancestry. Keep the observed IDs when reporting what was filtered. Unknown coverage
from another source is not an empty set and must not be used to discard inputs.
