# Research review of the remaining weaver recommendations

Reviewed 2026-10-10 against local revision `f868937`, the current specs/backends,
provider documentation, primary publications, and bounded live probes.
Scope: all **19 decision issues** in the previous recommendation list. This is a
research judgment, not approval or implementation of those features. Publishing,
persistent cache/resume, and the settled #262/#298 work are outside this decision
review, except where they constrain a proposal.

## How to read the ratings

**Usefulness (U)** and **problem coverage (F)** are qualitative scores from 1 to 5.
U=5 means a direct, well-supported workflow or scientific correctness need; U=3
means worthwhile but more specialized. F=5 means the proposed scope addresses the
substantive finding; F=3 means it fixes only one part of a broader issue. These are
engineering judgments, not measured demand or usage-frequency statistics.

**Risk** describes the proposed implementation's likely effect on existing
callers, downstream identity, scientific semantics, source cost, and local builds:
low = additive and isolated; medium = needs explicit contracts/source or schema
work; high = a public migration or another weaver's assumptions are affected.
Ratings assume the boundaries below. No research can guarantee absence of regressions;
the preservation checks are requirements for later implementation, not tests run here.

| Issue | Revised minimum recommendation | U | F | Risk | Judgment |
|---|---|---:|---:|---|---|
| #193 PDBe | Normalize existing chain/range evidence; optional validation summary | 5 | 3 | Low–medium | Do the small mapping/quality scope; defer assemblies/ligands |
| #199 AlphaFold | Return observed PAE and pLDDT data URLs; retain coverage/metric meaning | 5 | 4 | Low | Strong first addition; no matrix downloads |
| #202 AlphaFold | List/describe API-returned model entries, explicitly scoped to that source | 4 | 3 | Medium | Useful; cannot promise archive-only fragment completeness |
| #206 QuickGO | Evidence, qualifier and aspect parameters with explicit annotation semantics | 5 | 4 | Medium | Strong, after a deliberate NOT/positive-summary policy |
| #207 QuickGO | Typed ontology relations and obsoletion detail in requested groups | 4 | 3 | Low–medium | Do term detail first; defer broad reverse annotation traversal |
| #212 Reactome | Requested hierarchy and typed participant references | 4 | 3 | Medium | Useful bounded expansion; defer reaction traversal |
| #219 STRING | Score threshold and functional/physical scope; species constraint if coherent | 5 | 4 | Medium | Do with explicit measurement scope; defer regulatory schema |
| #231 NCBI | Explicit current/merged/deleted identity handling | 5 | 3 | Medium | Prioritize history; local descendants remain separate |
| #234 GTDB | Tree-identified JSON paths and explicit incomparable pairs | 5 | 5 | High | Necessary correctness migration; requires caller updates |
| #240 GTDB | Representative accession plus source release/provenance | 4 | 3 | Low–medium | Do minimal metadata; defer broader quality/history |
| #246 BacDive | Strain list/describe via BacDive IDs, retaining strain-level evidence | 5 | 4 | Medium | Strong fit to provider API; avoid species-level trait substitution |
| #251 AGORA | Reconstruction list/describe from existing crosswalk; artifact availability explicit | 4 | 3 | Medium | Metadata can proceed; reliable remote SBML still depends on #298 |
| #264 Disbiome | Compact experiment/publication IDs first; exact disease reverse lookup later | 5 | 3 | Low first; medium later | Evidence IDs are the clear win; reverse traversal needs disease identity |
| #272 GMrepo | Retain already-returned run/project/QC/host metadata before new capabilities | 5 | 4 | Medium | Revised: keep observed metadata first, then exact run drill-down |
| #278 MONDO | Direct MONDO-ID describe, definition and obsolete/replacement distinctions | 5 | 4 | Medium | Strong; mapping expansion should use canonical typed SSSOM |
| #286 Wikidata | Stable QID/taxid entry, separate localized labels from English title join | 5 | 4 | Medium; high if join changed | Stable IDs first; do not generalize the English title key silently |
| #295 Wikipedia | Requested monthly series and title provenance, using existing parameters | 4 | 3 | Low–medium | Revised: windows/agent already exist; keep English project fixed |
| #296 Disbiome | Exact sample/method/outcome filters, with explicit missing-value behavior | 4 | 4 | Medium | Useful narrow filters; defer rank/ancestor inference |
| #297 FAPROTAX | Requested explanation tracing ordered rules and references | 4 | 5 | Low–medium | Useful interpretability addition; never imply measured function |

## Findings that changed the original recommendations

- Wikipedia already declares `months`, `end_month`, and `agent`; its measurement
  output already records requested/observed bins and completeness. #295's title is
  historical. Reimplementing those parts would add complexity without benefit.
- GMrepo already consumes `disease.mesh.id` in `sample_profiles`. A live, one-run
  listing returned metadata that its acquisition currently reduces to run IDs.
  Keeping that evidence is a smaller first step than adding a fresh list capability.
- PDBe already retains all distinct observed chain rows under `chains`/`source`.
  #193 is now about convenient normalization and additional quality/detail, not
  recovering evidence currently lost by the implementation.
- AlphaFold already emits coverage inside its records after #197. It currently
  discards observed `paeDocUrl` and `plddtDocUrl`; those references are a small win.
  API model enumeration does not cover the documented archive-only long fragments.
- STRING's current documentation includes regulatory networks with directed output
  fields. Adding every documented enum to the existing symmetric mapper is unsafe.
- `wikipedia.title` is registered as an **English** article title. Wikidata language
  changes cannot safely reuse it for non-English titles while Wikipedia stays English.
- MONDO's provider now identifies SSSOM as the canonical mapping artifact. “All
  mappings” cannot safely mean untyped xrefs or blanket equivalence.

## Per-issue evidence, value, limits and preservation checks

### #193 — PDBe mapping and quality

**Evidence.** [PDBe's API overview](https://www.ebi.ac.uk/pdbe/pdbe-rest-api)
describes entry, mapping, quality and assembly access. Its
[API migration notice](https://www.ebi.ac.uk/pdbe/news/unifying-pdbe-api-endpoints-breaking-changes-pdbe-api)
means new endpoint assumptions need current validation. A live
[`best_structures/P04637`](https://www.ebi.ac.uk/pdbe/api/mappings/best_structures/P04637)
response contained 682 chain rows, including `start`, `end`, `unp_start`, `unp_end`,
coverage and resolution. Current `_extract` retains source rows and chains but
does not normalize those range fields; `_describe` is entry summary only.

**Value and scope.** Knowing which protein region a structure covers is directly
useful when selecting a structure or relating an experiment to a sequence. Add
documented coordinate namespaces and observed spans to existing chain evidence;
add method-appropriate validation metrics in a requested group. A span from a
best-structure endpoint is not a full residue alignment. Obtain entity IDs from a
documented mapping response rather than inventing them from the current rows.

**Preserve.** Keep ranking, display caps, full identifier fan-out, and entry-summary
requests unchanged. Do not flatten multiple chains or compare unlike validation
metrics as one universal score. Checks: overlapping/disjoint ranges, chain
identity, unchanged ranking, missing metric values, and zero extra quality calls
when the group is unrequested. Assemblies, ligands and full residue alignment remain
distinct remaining scope; this small addition cannot close all of #193.

### #199 — AlphaFold confidence references

**Evidence.** The live
[`prediction/P04637`](https://alphafold.ebi.ac.uk/api/prediction/P04637) response
included `paeDocUrl` and `plddtDocUrl`, alongside coordinate URLs and pLDDT
fractions. The [provider FAQ](https://www.alphafold.ebi.ac.uk/faq) distinguishes
local per-residue confidence from confidence in relative placement. Current
`_extract` already retains mean pLDDT, fractions and coverage, but omits both raw
confidence data URLs.

**Value and scope.** Emit observed URLs and their model version/sequence coverage
in requested confidence metadata. This supports domain-placement and residue
confidence analysis without loading potentially large matrices during a lookup.
Do not promise parsed arrays: references only partly cover that wider request.

**Preserve.** Use provider-supplied URLs, not guessed filename rewrites. Keep model
selection and the old outputs unchanged; missing URLs stay missing. Checks:
no downloads of linked payloads, absent references, distinct model versions, and
correct pLDDT versus PAE descriptions. A mean pLDDT is not a per-residue vector.

### #202 — AlphaFold model exploration

**Evidence.** P04637 returned nine entries with distinct model IDs, including
isoform-shaped accessions. The [provider downloads page](https://www.alphafold.ebi.ac.uk/download)
documents long-protein fragments distributed in human proteome archives rather
than the website. A bounded Q8WZ42 API probe returned 404. Neither that single
404 nor the P04637 list proves universal provider coverage.

**Value and scope.** Add list/describe for **API-observed entries**, retaining
entry ID, version, provider identity, sequence coverage and coordinate/reference
URLs. Useful for comparing available isoforms/models. It does not fully solve
fragment exploration: defer an archive backend and state the API coverage limit.

**Preserve.** Keep the representative lookup and its ranking unchanged. New model
identifiers must be registered shared keys paired with a consumer. Deduplicate
by the full model identity, retain a full observed ordered fan set, bound expansion,
and scope counts to retrieved entries. Checks: same accession with multiple
versions/isoforms, deterministic ordering, missing API entries, and unsupported
direct-ID lookup. Verify the provider's direct-ID route before promising it.

### #206 — QuickGO annotation filters

**Evidence.** [EBI's QuickGO training](https://www.ebi.ac.uk/training/online/courses/goa-and-quickgo-quick-tour/what-is-quickgo/viewing-go-annotations/)
documents evidence, qualifier, aspect and taxon filters. Live annotation probes
returned rows with evidence, reference, qualifier and taxon; an exact
`ECO:0000269` query returned that code. The [GO annotation specification](https://www.geneontology.org/docs/go-annotations/)
defines NOT as negative evidence. Current extraction collapses rows to term IDs
and aspect names, without an explicit qualifier interpretation.

**Value and scope.** Evidence/qualifier/aspect parameters support choosing an
annotation set for a particular analysis. Define evidence-code namespace and
exact-versus-descendant matching explicitly. Preserve raw evidence, including
negative annotations, in records; decide deliberately whether term-name summaries
are positive-only. A filter is not an evidence-strength ranking or a universal
“experimental is best” rule. Taxon is lower priority for exact UniProt inputs.

**Preserve.** Omitted filters should retain existing retrieval scope except for
a separately justified correction if current summaries misrepresent NOT rows.
Do not quietly change defaults while exposing parameters. Checks: NOT and
positive rows for the same term, multiple evidence rows, exact/descendant ECO
matching, pagination coverage, bulk correlation and distinct effective cache keys.
This is medium risk because biological interpretation can change, not because the
HTTP parameter plumbing is difficult.

### #207 — QuickGO ontology and reverse annotation lookup

**Evidence.** [QuickGO's API](https://www.ebi.ac.uk/QuickGO/api/) covers ontology,
annotations and gene products. The live GO:0006915 term response has typed
`children` and `isObsolete`; an ancestors request returned IDs including the queried
term itself. GO relations have different meanings; the
[GO annotation documentation](https://www.geneontology.org/docs/go-annotations/)
also distinguishes propagation behavior.

**Value and scope.** Requested typed relations and obsoletion detail make an
already-produced GO ID drillable beyond its name. Derive neither “parent” from
children nor all edge types as interchangeable ancestry. A direct parent contract
needs the correct source route. Reverse term-to-products is useful but potentially
large and is a separate bounded retrieval contract; defer it here.

**Preserve.** Keep existing term description and annotation lists unchanged;
extra requests occur only for requested relations. Checks: typed is_a/part_of,
self in ancestor responses, obsolete terms, missing replacement information,
deduplication and limits. Replacement targets should be emitted only when observed,
not inferred from a related term.

### #212 — Reactome pathway detail

**Evidence.** [Reactome's Content Service guide](https://reactome.org/dev/content-service/)
describes pathways, events and physical entities. Its older participant example
returned 404 in a probe, while the current
[`data/participants/R-HSA-141409`](https://reactome.org/ContentService/data/participants/R-HSA-141409)
route returned three participants with `peDbId`, `schemaClass` and `refEntities`.
One reference contained UniProt Q9Y6D9. Current detail retains only basic summary
attributes; listing evidence was already improved in #214.

**Value and scope.** Requested direct hierarchy and participant references help
explain a pathway and join to molecular information. Preserve participant type:
complexes, sets and molecules are not all proteins. Reference stable identifiers
where present; release-scope provider numeric IDs. Recursive reaction expansion
and full evidence interpretation remain separate work.

**Preserve.** Summary calls must not download a whole species hierarchy or perform
unrequested expansion. Checks: mixed physical entity types, absent stable IDs,
release provenance, deterministic deduplication, endpoint correlation and group-only
requests. This is medium risk due to additional source calls and entity semantics.

### #219 — STRING parameters

**Evidence.** [STRING's current API documentation](https://string-db.org/help//api/)
documents `required_score`, species and functional/physical/regulatory network
types for interaction partners. Request thresholds use 0–1000; output scores use
their documented scale. Regulatory output has directed fields. Current backend
uses the pinned 12.5 service and keeps bounded-partner coverage, but does not
declare these per-query parameters.

**Value and scope.** Add score threshold and functional/physical selection with
explicit scope in evidence/coverage. A species override should constrain identity
mapping consistently, never silently remap an accession to a homolog. The default
should remain the existing functional retrieval behavior. Defer regulatory/typed
networks until direction, sign and mapper fields have their own contract.

**Preserve.** Do not apply a 0–1000 threshold to an already-normalized 0–1 score.
Keep mixed-species batching valid when no species constraint is supplied. Checks:
same IDs under different network scopes, thresholds/boundaries, species conflict,
parameter cache isolation and unchanged default requests. “Physical” remains a
provider prediction, not proof of experimentally measured binding.

### #231 — NCBI historical IDs and local descendants

**Evidence.** [NCBI's Taxonomy reference](https://www.ncbi.nlm.nih.gov/sites/books/NBK53758/pdf/Bookshelf_NBK53758.pdf)
distinguishes `merged.dmp` secondary-to-primary IDs and `delnodes.dmp` deleted IDs;
`nodes.dmp` records parent relationships. Current bundled fixture uses nodes/names,
and the issue's historical/local capability proposals remain open after #230's
protocol and JSON work.

**Value and scope.** Retain requested/current IDs and current/merged/deleted status
with the dump identity. Merge chains may resolve deterministically to a current
ID; deletion is not replacement, ambiguity or network failure. This helps reproduce
old datasets. Local descendants are a separate useful offline parity feature,
with direct-children versus all-descendants and rank/depth/limit scope made explicit.

**Preserve.** Keep live/backend capability support truthful; optional operations
remain structural interfaces. Do not overwrite a caller's old ID without recording
the mapping, or fabricate a successor for deleted IDs. Checks: chained/cyclic merge
records, missing history files, deleted versus unknown, backend parity and dump
fingerprints covering history. Missing history files must mean history unavailable,
not “this ID was never present.” History alone only partially covers #231.

### #234 — GTDB tree comparability

**Evidence.** [GTDB's FAQ](https://gtdb.ecogenomic.org/faq) describes separate
bacterial and archaeal trees inferred with different marker sets/models.
Current `cophenetic` returns the sum of root depths when paths share no root and
its docstring calls this a valid maximally distant answer. Node IDs are assigned
from traversal order. A numeric distance between disconnected trees is not
defined by these input trees; that conclusion follows from the algorithm and
source construction, not a provider-endorsed cross-domain distance method.

**Value and scope.** Serialize tree/content identity, release, leaf identity and
path steps; compare only compatible paths. Return an explicit incomparable outcome
with a reason, not zero, an invented maximum or silently usable NaN. Preserve the
valid same-tree patristic calculation. Domain objects stay in GTDB, not core.

**Preserve.** This intentionally changes a public value/helper contract and needs
an explicit migration of callers. Same tree identity must imply stable node
numbering: use tree-local IDs or canonical enumeration, independent of the order
other trees were supplied. Checks: same tree across instances and JSON, different
releases, permuted forest order, disconnected domains, invalid paths and unchanged
valid distances. External dependent projects have not been inspected or changed
in this research; “no outside damage” cannot be promised until they migrate.

### #240 — GTDB genome metadata

**Evidence.** [GTDB's downloads](https://gtdb.ecogenomic.org/downloads) and
[FAQ](https://gtdb.ecogenomic.org/faq) provide metadata and representative-genome
selection semantics. Current crosswalk already stores representative accession
and release, but its public taxonomy output contains taxon/lineage only.

**Value and scope.** Expose the selected representative accession with release and
the relation “representative of this GTDB species.” This supports fetching the
right reference genome. Do not present it as the input strain's own assembly.
Quality can follow later: it belongs to a particular genome and method, not an
unqualified species-quality score. Cross-release taxonomy names are not immutable
identifiers; broader synonym/history requires source-specific evidence.

**Preserve.** Reuse the existing local index without new downloads for the minimal
group. Keep ambiguous classifications and taxonomy outputs unchanged. Checks:
missing representatives, representative distinct from input genome, release
changes and ambiguous species. New routable assembly outputs need explicit fan
semantics and key registration; a record field alone is a smaller first change.

### #246 — BacDive exact strain workflows

**Evidence.** [BacDive's current API guide](https://hub.dsmz.de/wiki/bacdive/api/)
documents taxon-to-strain IDs, exact fetch in batches of up to 100, culture
collection lookup and genome accession lookup. API v2 is keyless; the current
weaver already uses it. A live strain 5621 fetch returned morphology, sequence,
isolation and other source sections. Existing public trait lookup takes a
scientific name and chooses source evidence, rather than accepting exact strain IDs.

**Value and scope.** Add strain list/describe with BacDive IDs and observed culture
collection/genome references. This fits provider shape and prevents confusing
a species representative's trait with evidence about every strain. Exact culture
collection mapping can follow once multiplicity and normalized identifiers are
specified; never assume one collection number implies one universal strain ID.

**Preserve.** Keep current name-based selection behavior and scalar traits intact.
Exact strain results do not overwrite species-level claims from another source.
Checks: multiple strains, type/non-type identity, per-strain conflicting traits,
pagination, full fan set, 100-ID chunking and unknown IDs. No new authentication
flow or provider SDK dependency is necessary.

### #251 — AGORA reconstruction bridges

**Evidence.** The [AGORA2 primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10497413/)
describes strain-resolved metabolic reconstructions; the
[provider repository](https://github.com/VirtualMetabolicHuman/AGORA2) points to
external VMH downloads. Current core lookup already returns reconstruction and
genome IDs inside records, and artifact validation is implemented. Individual
acquisition remains unresolved in #298.

**Value and scope.** A reconstruction list/describe pair can expose the existing
crosswalk as typed model identity without downloading SBML. Exact description can
report metadata and honestly distinguish cached artifact, consent required and
unavailable remote acquisition. Genome links should retain exact model/strain
association. General reaction routing is a different entity contract.

**Preserve.** Register and consume a release-qualified reconstruction key; retain
existing organism results and consent behavior. Merely listing models must not
start model/large archive downloads or claim a solver result. Checks: several
models per taxid, absent/cached artifacts, source/version mismatches and uncapped
identifier set versus capped presentation. Remote SBML availability is still a
dependency, so the whole model workflow cannot be marked fixed by new routing.

### #264 — Disbiome evidence identity and reverse disease traversal

**Evidence.** The [Disbiome primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC5987391/)
identifies experiments, publications, organisms, samples and detection methods as
linked evidence. [Provider export documentation](https://disbiome.ugent.be/export)
describes those JSON records. Current full output keeps joined evidence, while
compact `_association_row` drops experiment/publication identities.

**Value and scope.** First retain experiment/publication/organism IDs in compact
associations, with known quality context or references to full records. This allows
tracing apparently conflicting observations to studies. Exact disease-to-observed
taxa is useful but needs provider disease ID versus MedDRA relationship semantics.
Different disease records/codes must not collapse merely because names match.

**Preserve.** Do not change summary counts or aggregate genus measurements into
species claims. If compact columns change, migrate/rebuild schema explicitly while
retaining SQL projection cost benefits. Checks: same taxid/disease across studies,
missing publication, genus observations, code multiplicity and unchanged summaries.
Disease bridge/reverse capability remains a separate decision after compact IDs.

### #272 — GMrepo metadata and cohort traversal

**Evidence.** The [GMrepo v3 primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12807640/)
describes curated metadata and cross-project disease comparisons;
[provider project/run documentation](https://evolgeniusteam.github.io/gmrepodocumentation/websiteandUI/projectandrunpages/)
explains the entities. A bounded live one-run listing for D003093 returned run,
sample and project IDs, `QCStatus`, host age, country, sex and sequencing fields.
Current `_fetch_run_ids` discards those fields; `sample_profiles` already accepts
MeSH IDs.

**Value and scope.** Retain source run metadata alongside profiles, then offer
exact run description if callers need standalone drilling. This addresses cohort
interpretability without an additional upstream request per run. Add provider
phenotype IDs to taxon association records before introducing a new disease bridge.
Filters must describe selection before the acquisition cap, not pretend filtering
an already capped local subset yields a complete cohort.

**Preserve.** Separate run/sample/project IDs; retain source units and unknown
values. Do not reinterpret QC labels or medical metadata as universally comparable.
Coverage must state requested/selected/failed/empty runs and selection scope.
Checks: missing metadata, conflicting versions, repeated run IDs, cap/filter order,
cohort denominator and unchanged default profiles. No statistical biomarker
inference or uncapped acquisition belongs in this metadata change.

### #278 — MONDO direct-ID description and history

**Evidence.** [MONDO's FAQ](https://mondo.monarchinitiative.org/pages/faq/)
says obsolete IDs are retained rather than deleted. Its
[obsoletion guide](https://mondo.readthedocs.io/en/stable/editors-guide/merging-and-obsoleting/)
distinguishes replacement and consider annotations. The provider's
[canonical mapping notice](https://github.com/monarch-initiative/mondo/issues/9921)
identifies `mondo.sssom.tsv` as the current mapping source. Current OBO loader
drops obsolete terms and omits definitions/replacement details; its public lookup
cannot consume an already-produced MONDO ID.

**Value and scope.** Add direct-ID description and retain definition plus explicit
current/obsolete/replaced/consider status. A suggestion is not an automatic successor.
Keep current terms in resolution indexes while storing obsolete terms for description.
Mapping expansion should separately read release-matched SSSOM with predicates and
provenance; return typed mapping records rather than claim all xrefs are equivalent.

**Preserve.** Existing ambiguity/review rules remain intact. Obsolete concepts do
not become ordinary name matches. Checks: current/obsolete IDs, no replacement,
consider targets, mismatched releases, contradictory mapping predicates and JSON
round-trip. This fully addresses direct-ID/history needs but leaves broader mapping
coverage as a distinct ingestion step.

### #286 — Wikidata stable IDs and language

**Evidence.** [Wikidata P685](https://www.wikidata.org/wiki/Property_talk:P685)
represents NCBI taxonomy IDs. [Wikibase's API](https://www.mediawiki.org/wiki/Wikibase/API)
supports direct entity IDs; its [presentation guide](https://www.mediawiki.org/wiki/API:Presenting_Wikidata_knowledge)
separates language-filtered labels/descriptions, fallback and site-filtered
sitelinks. Current weaver resolves P225 scientific names and emits an enwiki title;
the shared registry explicitly defines that title key as English.

**Value and scope.** Prefer QID description and exact P685-to-QID mapping over more
name heuristics. P685 absence or multiple items needs explicit no-match/ambiguity,
not one arbitrary pick. Localized labels can be a parameter while the existing
English page title remains coherent. A multilingual article reference needs its
own project-qualified identity and coordinated Wikipedia support; defer that here.

**Preserve.** Name resolution/candidate review and English title routing remain
unchanged. Separate requested versus actual fallback language. Validate QID/taxid
and language values without query interpolation risks. Checks: duplicate P685,
missing/redirected QIDs, absent labels/sitelinks, multi-language batches and
Wikidata→English-Wikipedia integration. Unqualified non-English titles would be
high cross-weaver risk, so that original broad language interpretation is rejected.

### #295 — Wikipedia series and title policy

**Evidence.** [Wikimedia's pageview reference](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html)
supports monthly observations. Its [measurement definition](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/concepts/page-views.html)
distinguishes agent traffic and redirect behavior. The current spec already
declares `months`, `end_month`, `agent`; `measurement.py` records scope/completeness.
API output reduces observed bins to a subtotal; local backend supports a single
user-traffic dump month.

**Value and scope.** Add a requested series group using already-returned monthly
bins, plus input/requested/canonical title provenance if normalization is added.
Keep project/access fixed for the first change. Distinguish resolving a redirect
to one target from aggregating all redirect-title traffic; neither should silently
rewrite the measurement's historical meaning.

**Preserve.** Keep subtotal semantics and existing defaults, and never fill absent
bins as measured zero. A local series supports only acquired months, with explicit
scope or an unsupported request outcome. Checks: sum equals observed subtotal,
partial bins, ordering, title escaping, completed-month bounds and API/local
measurement parity. This is a smaller change than reintroducing existing knobs.

### #296 — Disbiome scientific filters

**Evidence.** [Disbiome's help](https://disbiome.ugent.be/help) and
[primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC5987391/) describe sample,
method, host and qualitative outcomes. Current local database already stores
sample/method/outcome projection columns. Source rank is not currently a reliable
explicit field for all evidence, so a rank filter cannot simply trust the input key.

**Value and scope.** Add exact sample/body-site, method and qualitative-outcome
filters only where those are distinct observed fields. Do not rename sample type
as anatomical site: location may be a separate source join. Start with existing
`sample_name`, `method_name`, `qualitative_outcome` fields; distinguish unknown,
any and an exact value. Defer rank filtering/ancestor policy until evidence rank
is sourced consistently. No silent taxonomy climb belongs in filtering.

**Preserve.** Omitted filters retain today's associations. Filtering precedes counts,
name deduplication and presentation caps, with evidence retained per experiment.
Checks: missing source values, conflicts across studies, summary/full agreement,
all-filtered-out versus acquisition error, exact taxid and effective cache keys.
These filters improve interpretability but do not establish causation or combine
heterogeneous detection methods into one inferred effect.

### #297 — FAPROTAX public explanations

**Evidence.** The [provider description](https://pages.uoregon.edu/slouca/LoucaLab/archive/FAPROTAX/lib/php/index.php)
defines taxonomic-to-putative-function inference from cultured-strain literature.
The bundled source documents ordered add/subtract/intersect operations and group
attributes. Current private parser retains rule references/line numbers and group
attributes; the evaluator returns membership only. Prior differential verification
established matcher parity, not direct experimental validation of a queried organism.

**Value and scope.** Add a requested evidence group showing input lineage, source
identity, relevant ordered rule operations, matched patterns and retained literature.
The explanation should come from the same evaluator as membership, not a separate
approximation. Exclusions and intersections can change the result after a positive
pattern. Some referenced groups contribute without a direct member pattern.

**Preserve.** Existing function names/order and default lookup cost remain unchanged.
Requested traces can reuse membership work without evaluating every rule twice;
return plain JSON values, not private dataclasses/regexes. Checks: subtract then
re-add, nested groups, intersection, absent references, false membership and default
output equality. Trace provenance is not a measured phenotype or a numerical
confidence score. Keep source notices and licensing intact.

## Recommended staging and containment

1. **Small additions using evidence already fetched:** AlphaFold confidence links
   (#199), PDBe range normalization (part of #193), Disbiome compact IDs (part of
   #264), GMrepo metadata retention (part of #272), GTDB accession/release (part
   of #240), Wikipedia series (part of #295), FAPROTAX trace (#297).
2. **Scientific/public contract fixes:** GTDB comparable paths (#234), NCBI history
   (part of #231), MONDO direct-ID/history (part of #278). GTDB is urgent but needs
   its consumer migration planned explicitly; it should not be disguised as a
   compatibility-preserving additive output.
3. **Parameters and controlled entity traversal:** QuickGO filters/relations,
   STRING scopes, BacDive strain drilling, API-scoped AlphaFold models, Reactome
   participants/hierarchy, Disbiome filters and stable Wikidata IDs.
4. **Separate larger choices:** reverse disease/GO traversal, archive-only AlphaFold
   fragments, regulatory STRING edges, full MONDO mappings, multilingual Wikipedia
   project identity and broader genome/reaction bridges. AGORA model metadata does
   not require remote downloads; remote model retrieval remains tied to #298.

Across these scopes, keep biology in source packages, prefer small pure parsers and
projections plus existing templates, and add public classes only for real serialized
values such as tree identity. No shared framework rewrite is warranted by this review.
New capabilities go through spec/scaffold/selective regeneration, and new bridges
through the shared-key registry. Output groups gate cost; list outputs distinguish
retrieved coverage from complete source enumeration. Tests must preserve existing
contracts and explicitly verify cross-weaver routing where identities change.

## Research observations and limits

Eleven bounded requests were made with a 500 KB response-read cap, a 15-second
timeout and at most four concurrent workers. Two targeted QuickGO/AlphaFold
requests per source were concurrent; no multi-GB archive, scientific environment
installation or new runtime dependency was used. Raw responses and probe scripts
are in ignored `.audit-local/research/`; the compact non-dataset observations are
retained in [recommendation-probes.json](recommendation-probes.json).

| Probe | Result | Interpretation |
|---|---|---|
| AlphaFold P04637 | 200; nine entries; observed PAE/pLDDT URLs | Metadata and model enumeration supported for this example |
| AlphaFold Q8WZ42 | 404 | No API entries in this probe; archive completeness not claimed |
| QuickGO GO:0006915 | 200; typed children and obsolete flag | Observed term relations are available |
| QuickGO aspect annotation filter | 200 | Endpoint accepted query and returned annotation fields; not full filter certification |
| QuickGO exact ECO evidence filter | 200; returned ECO:0000269 | One observed exact-code case works |
| QuickGO ancestors | 200; self present in ancestor list | Self/relationship semantics require normalization |
| BacDive strain 5621 | 200; source sections returned | Exact strain retrieval works for this example |
| Reactome older documented participant route | 404 | Old example is not a live endpoint guarantee |
| Reactome current participants route | 200; typed entities/reference records | Useful route verified for this example |
| PDBe best structures P04637 | 200; 682 source rows with ranges | Mapping data already fetched can be projected |
| GMrepo disease run listing, limit=1 | 200; host/QC/project metadata present | Metadata can be retained without another per-run request |

Primary publications establish intended workflows, not their popularity. Dynamic
web pages sometimes exposed only indexed text; documentation and individual probes
do not certify every endpoint, obsolete-ID case, dataset release or backend.
No product code, public contract, dependent project or GitHub issue state changed
as part of this research. Later implementation still requires meaningful package,
strict, workspace and changed-API live checks.
