# Weaver audit decision stack

The [2026-10-10 research review](recommendation-research.md) evaluates all 19
decision issues against current code and primary sources. Its narrower recommendations
and risk boundaries supersede the preliminary recommendations below. In particular,
Wikipedia already has window/agent parameters, GMrepo already has disease input,
and localized Wikidata titles cannot reuse the English Wikipedia join key.

Settled correctness and documentation issues proceed in batches. This stack collects scope/API choices for review after that work; it is not a claim that every other open issue needs a decision.

| Issue | Context | Recommendation | Decision needed |
|---|---|---|---|
| [#193](https://github.com/rafaelmdc/braidworks/issues/193) — PDBe mapping/quality | Original chain evidence is retained, but richer residue mapping and quality groups are new output scope with different upstream costs. Assembly and ligand records have different entity shapes. | Add stable normalized mapping and a separate quality group; treat assembly/ligand capabilities as separate future work. | Which new output scope should this round include? |
| [#234](https://github.com/rafaelmdc/braidworks/issues/234) — GTDB distance comparability | Current root paths contain node IDs and depths, without a tree/release identity. Summing depths across disconnected trees is not a scientifically defined patristic distance; paths from different releases can accidentally share node IDs. | Introduce a serializable path value carrying tree/release identity and reject incomparable paths explicitly. Update the dependent project rather than retain ambiguous numerical behavior. | Confirm the public path migration and how callers represent incomparable pairs. |
| [#199](https://github.com/rafaelmdc/braidworks/issues/199) — AlphaFold confidence | Existing output links a PAE image; machine-readable PAE and residue-confidence references would add useful analysis inputs. Large matrices need not be fetched during a lookup. | Add observed raw-data URLs and coverage/confidence metadata in a requested output group, with metric semantics documented. | Include these new references and fields in this round? |
| [#202](https://github.com/rafaelmdc/braidworks/issues/202) — AlphaFold model exploration | A representative lookup currently returns one model, so callers cannot explore all fragments or alternative models. Correcting representative coverage (#197) can proceed independently. | Add paired list_models/describe_model capabilities with stable model IDs and bounded fan-out. | Include the new capabilities now or defer them? |
| [#206](https://github.com/rafaelmdc/braidworks/issues/206) — QuickGO annotation filters | Evidence, qualifier and aspect filters change which annotations a query returns. Existing defaults should preserve the current results. | Declare source-backed parameters with deterministic defaults and preserve raw evidence. | Which scientific filters should this round expose? |
| [#207](https://github.com/rafaelmdc/braidworks/issues/207) — QuickGO ontology/reverse lookup | Term relations and reverse term-to-gene-product lookup are additional workflows with different cardinalities. | Add typed term relations first; scope reverse annotation traversal separately with retrieval limits. | Include ontology relation detail, reverse lookup, or both? |
| [#212](https://github.com/rafaelmdc/braidworks/issues/212) — Reactome richer pathway detail | Hierarchy, participants, reactions and evidence require additional outputs and potentially extra requests. Listing evidence is now retained under #214. | Add requested hierarchy/participant groups with stable IDs and explicit coverage; scope reaction expansion separately. | Which detail groups should be included? |
| [#219](https://github.com/rafaelmdc/braidworks/issues/219) — STRING query parameters | Score, network type and species are source knobs. Physical and functional networks have different meanings; current outputs describe functional associations. | Declare supported parameters while retaining current defaults; document each network meaning and score scale. | Which knobs should be public in this round? |
| [#231](https://github.com/rafaelmdc/braidworks/issues/231) — NCBI descendants and historical IDs | Extension/version documentation can be corrected independently. Local descendants and merged/deleted taxid handling change supported workflows and historical-ID policy. | Fix docs first; add explicit current/replaced/deleted status before optional local descendant parity. | Include historical-ID handling and/or local descendants? |
| [#240](https://github.com/rafaelmdc/braidworks/issues/240) — GTDB genome metadata | Tree usage and limitations need accurate docs. Representative accession, quality, synonyms and release outputs would add new public fields. | Correct docs first; expose stable representative accession and release in a requested group before quality expansion. | Which genome metadata should this round expose? |
| [#246](https://github.com/rafaelmdc/braidworks/issues/246) — BacDive exact strain workflows | Scope/group documentation can be fixed now. Exact strain IDs, culture collection mappings and isolation/genome fields are new workflows. | Add paired strain list/describe using stable BacDive IDs; preserve taxonomic granularity. | Include strain drilling and which cross-references? |
| [#251](https://github.com/rafaelmdc/braidworks/issues/251) — AGORA model and reaction bridges | Current reaction/genome IDs sit inside records. Making them routable requires keys and entity-specific contracts; model download reliability is tracked separately in #298. | Pair model list/describe first; evaluate genome bridge separately and avoid calling leaf reaction records routable. | Which bridges should be added after acquisition is verified? |
| [#264](https://github.com/rafaelmdc/braidworks/issues/264) — Disbiome evidence and disease direction | Compact evidence identifiers can be retained independently. A disease-to-microbe join or reverse capability adds a direction and requires a disease-identity contract. | Keep experiment/publication IDs, then spec a disease bridge and reverse listing from observed provider identity. | Include disease/reverse traversal now? |
| [#272](https://github.com/rafaelmdc/braidworks/issues/272) — GMrepo runs and disease bridges | Run/project/QC/host metadata and cohort filters are additional output/query contracts; MeSH identifiers currently remain inside associations. | Add paired run list/describe with source-backed metadata, then disease bridges with explicit cohort scope. | Which metadata and cohort knobs should be public? |
| [#278](https://github.com/rafaelmdc/braidworks/issues/278) — MONDO direct ID description | Resolved MONDO IDs cannot currently be drilled through a dedicated describe capability. Definitions and obsolete/replacement/mapping detail add fields. | Add direct-ID describe with explicit current/obsolete/replaced/consider distinctions. | Include definitions and all mapping relations in that first capability? |
| [#286](https://github.com/rafaelmdc/braidworks/issues/286) — Wikidata stable IDs and language | Name lookup alone limits identity precision. QID/NCBI entry and configurable language introduce new input/output contracts. | Prefer stable-ID mapping plus QID description; make language a parameter with coherent title/project provenance. | Include both stable-ID entry paths and language support? |
| [#295](https://github.com/rafaelmdc/braidworks/issues/295) — Wikipedia temporal and title policy | Safe docs can improve independently. Time series, agent/access/project/window knobs and redirect policy need a query scope choice. | Start with explicit monthly window and title normalization provenance; keep source/project and redirect identity coherent. | Include series now, and which caller knobs? |
| [#296](https://github.com/rafaelmdc/braidworks/issues/296) — Disbiome scientific filters | Rank, body-site, method and outcome filters require rules for missing evidence and taxonomic granularity. The repeated-work fix is already complete. | Declare a small set of observed filters with explicit unknown-value handling and unchanged default results. | Which evidence filters should be supported? |
| [#297](https://github.com/rafaelmdc/braidworks/issues/297) — FAPROTAX public evidence | Group attributes and literature are now preserved privately. Public explanations must reflect ordered exclusions/intersections rather than only a direct matching pattern. | Expose a separate requested evidence group with matching rules, literature and group attributes. | Add that public evidence group now? |

The current source queue has been screened. These choices remain separate from correctness fixes; mixed documentation issues can still receive documentation corrections before the feature decision. Publishing and persistent cache/resume remain deferred (#142/#143).

## Completed correctness batch

#195, #277, #271 and #237 are closed with separate local commits. Workspace lint/test passed (2045 pytest cases, 56 skips, plus tool unittest checks); strict verification passed for the changed weavers. At that point AlphaFold #197 was next. The source count was later reconciled with GitHub: #223 had already closed during earlier work. Current counts appear below.

## Work that can proceed without a scope question

- #265 is complete: Disbiome build shape/identity/join validation and source coverage provenance (local commit acb4ad0).
- #262: Correct Disbiome exact generic/genus/species taxid inputs and preserve evidence rank. Optional ancestor roll-up is a separate future scope; it must not imply a genus measurement for every species.
- #298: Research and verify AGORA's individual model acquisition source; malformed HTML remains an error.
- Mixed docs/feature issues (#231/#240/#246/#251/#295) can receive accurate docs without approving their optional features.

Publishing and durable cache/resume remain deferred (#142/#143).

## Pack of 10 completed

#197, #214, #221, #230, #249, #254 and #256–#259 are implemented with local commits.
#297 retains the optional FAPROTAX evidence choice; #298 tracks the observed AGORA
acquisition failure. The latter needs source research, not a user decision. Nineteen
original source findings remain, plus #296/#297/#298 follow-ups. Nothing is pushed.

## Disbiome follow-on

#265 closed; #262 exact routing committed in d8f8ce4, with rank coverage still open.
Package version 0.3.6: 44 tests passed, strict verification and lint passed.
The final full workspace run passed 2102 pytest cases with 56 skips, plus
five tool unittest checks; workspace lint and strict verification passed.
Eighteen original source findings remain, plus follow-ups #296/#297/#298.
AGORA replacement acquisition remains unverified; no release or mirror changed.

Five additional source-identity regressions passed in the final 44-test Disbiome
package run; they were added after the workspace run reached Disbiome.
