# Weaver audit issue hierarchy and second-pass review

Date: 2026-10-08. Programme [#147](https://github.com/rafaelmdc/braidworks/issues/147).
Existing audit parent reused; no duplicate programme issue. **122 findings, 26 group
issues, 148 new issues**. All are native GitHub sub-issues, not just checklist links.
Runtime work has not started. [Machine-readable mapping](issue-map.tsv).

## Second-pass method and result

Reviewed all 122 register rows against the source reports, proposed acceptance
specifications and matching work packages. Rechecked representative source code for
configuration, fingerprint settings, group costs and the NCBI build/CLI paths.
Reran all eight retained offline probes: each completed and still demonstrates the
documented behavior. Checked existing repository issues for overlap before creation.
This is a grouping/evidence/acceptance review, not a new full live-service certification.

The original six shared themes missed three recurring concerns: semantic source
identity/coherent resource selection, stable identity/deterministic collections, and
group-aware measured work. No new finding IDs or unverified bugs were invented.
There are now **9 shared groups with 81 primary findings**, and **17 source-specific
groups with 41 primary findings**. Each finding belongs to exactly one group. Mixed
concerns link to additional groups rather than creating duplicate finding issues.

Shared means coordinated requirements, conventions or mechanics. It does not imply
all source-specific policies/parsers/selection rules belong in core. A stable sorting
invariant is shared; deciding whether MONDO mappings are equivalent is source-specific.
Source groups collect the remaining work per weaver, retaining optional feature and
performance decisions instead of promoting every proposal to an accepted requirement.

## Compatibility and scope

The user explicitly permits necessary breaking changes because current dependent
projects are theirs. Earlier compatibility-preservation recommendations in proposed
specs/plans are revisable. Prefer correct, truthful contracts; record affected capability
IDs, output keys/groups, input cardinality, parameters, serialization and CLI/Python
behavior. Update dependent projects/recipes and package version sites as appropriate.
This clarification does not approve every optional feature, change contracts merely
to pass tests, authorize publishing, or reopen deferred cache/resume implementation.

## Shared group issues

| Group | Issue | Primary findings | Coordinated boundary |
|---|---|---|---|
| SH-01: Safe scaffold regeneration and contributor guidance | [#148](https://github.com/rafaelmdc/braidworks/issues/148) | 4 | Fix the generated contributor instructions and apply safe scratch/diff/selective-update guidance to implemented packages. NCBI is handwritten and exempt from scaffold regeneration. Mixed config/docs findings reference this group without duplicating their issue. |
| SH-02: Explicit configuration and HTTP client ownership | [#149](https://github.com/rafaelmdc/braidworks/issues/149) | 16 | Honor supported configuration, reject misspelled/unsupported configuration, make source selection/defaults explicit and close only owned HTTP clients. Reuse a small lifecycle/config mechanism only when concrete implementations justify it. Source settings remain source-local. Mixed rows retain their docs/concurrency requirements. |
| SH-03: Validated source responses and isolated failure values | [#150](https://github.com/rafaelmdc/braidworks/issues/150) | 15 | Expected decoding/schema/upstream failures become correctly correlated record/chunk error values, without losing good siblings or swallowing cancellation/programming faults. Share mechanics only; endpoint-specific not-found semantics and schemas stay source-local. SPARQL syntax400 is not taxon absence. Current normal batch sizes do not reach PDBe/Reactome multi-chunk defects; keep direct-backend scope explicit. |
| SH-04: Truthful coverage and computed output groups | [#151](https://github.com/rafaelmdc/braidworks/issues/151) | 11 | Distinguish valid empty, unavailable, failed, truncated and complete results. Computed groups must represent actual work. Measurement scope/period/cohort and pagination budgets must be explicit. Assess existing record/warning APIs first; contract changes are allowed if needed. This does not authorize cache/resume implementation. |
| SH-05: Atomic complete database replacement | [#152](https://github.com/rafaelmdc/braidworks/issues/152) | 3 | All public complete-rebuild paths stage, validate and atomically replace resources, preserve existing targets on failure and remove obsolete rows on success. Reuse existing safe localdb staging; do not invent a parallel persistence framework. NCBI destructive path is P0. Source-specific streaming/provenance/cleanup requirements remain in each child. |
| SH-06: Bounded batching and polite acquisition | [#153](https://github.com/rafaelmdc/braidworks/issues/153) | 3 | Use supported bulk endpoints, deduplicate inputs and bound concurrent single-ID work. Apply source-specific pacing, retry and call budgets to acquisition as well as runtime paths. Preserve batch order/correlation/cancellation. Coordinate related concurrency aspects in SH-02 children; no implementation of incremental resume without later scope review. |
| SH-07: Semantic source identity and coherent resource selection | [#154](https://github.com/rafaelmdc/braidworks/issues/154) | 8 | Identify the effective endpoint, release, result-affecting limits/policies and requested resource scope without exposing secrets. Pin coherent multi-resource releases and validate requested month/version against actual metadata. Reuse SourceBinding; source descriptor choices remain source-specific. Fingerprint correctness is current work, not a durable-cache implementation. |
| SH-08: Stable identity, deterministic selection and distinct collections | [#155](https://github.com/rafaelmdc/braidworks/issues/155) | 15 | Correlate to stable identities, deduplicate by source identity and use deterministic ID tie-breaks. Do not turn ambiguity, non-equivalence or different taxonomic granularity into confident identity. Shared invariants/testing conventions are useful; selection and scientific mapping policies are source-specific and must not become a generic universal selector. |
| SH-09: Group-aware work and measured performance | [#156](https://github.com/rafaelmdc/braidworks/issues/156) | 6 | Avoid expensive unrequested group projection and unnecessary repeat parsing/SQL/source work. Measure bounded representative cases before adding memoization, batching or immutable projections. Keep optional P3 optimizations conditional on evidence; do not add a repository layer merely to match a pattern. |

## Remaining source-specific groups

| Weaver | Group issue | Primary findings |
|---|---|---|
| [example](example.audit.md) | [#157](https://github.com/rafaelmdc/braidworks/issues/157) | 4 |
| [uniprot](uniprot.audit.md) | [#158](https://github.com/rafaelmdc/braidworks/issues/158) | 3 |
| [pdbe](pdbe.audit.md) | [#159](https://github.com/rafaelmdc/braidworks/issues/159) | 2 |
| [alphafold](alphafold.audit.md) | [#160](https://github.com/rafaelmdc/braidworks/issues/160) | 3 |
| [quickgo](quickgo.audit.md) | [#161](https://github.com/rafaelmdc/braidworks/issues/161) | 2 |
| [reactome](reactome.audit.md) | [#162](https://github.com/rafaelmdc/braidworks/issues/162) | 2 |
| [string](string.audit.md) | [#163](https://github.com/rafaelmdc/braidworks/issues/163) | 2 |
| [ncbi](ncbi.audit.md) | [#164](https://github.com/rafaelmdc/braidworks/issues/164) | 3 |
| [gtdb](gtdb.audit.md) | [#165](https://github.com/rafaelmdc/braidworks/issues/165) | 3 |
| [bacdive](bacdive.audit.md) | [#166](https://github.com/rafaelmdc/braidworks/issues/166) | 1 |
| [agora](agora.audit.md) | [#167](https://github.com/rafaelmdc/braidworks/issues/167) | 3 |
| [faprotax](faprotax.audit.md) | [#168](https://github.com/rafaelmdc/braidworks/issues/168) | 4 |
| [disbiome](disbiome.audit.md) | [#169](https://github.com/rafaelmdc/braidworks/issues/169) | 3 |
| [gmrepo](gmrepo.audit.md) | [#170](https://github.com/rafaelmdc/braidworks/issues/170) | 2 |
| [mondo](mondo.audit.md) | [#171](https://github.com/rafaelmdc/braidworks/issues/171) | 2 |
| [wikidata](wikidata.audit.md) | [#172](https://github.com/rafaelmdc/braidworks/issues/172) | 1 |
| [wikipedia](wikipedia.audit.md) | [#173](https://github.com/rafaelmdc/braidworks/issues/173) | 1 |

## Existing programme coordination

- #144: persistence foundations; reuse existing staging/source-binding mechanisms.
- #136: HTTP pacing remediation; SH-06 covers source-specific acquisition gaps.
- #131: acquisition progress; source docs/build usability overlaps remain cross-references.
- #135: fan-out availability; related to coverage/identity, not a duplicate of every source defect.
- #67: generated capability documentation; coordinate template/doc work.
- #1: references/license metadata; AGORA restricted-license rendering is related.
- #143 and #142: cache/resume and publishing remain deferred; this issue hierarchy
  does not change their scope or state.

Existing broad programme issues are not closed or reparented by this bookkeeping.
Each new finding records its stable ID, priority, confidence, evidence, acceptance,
source work packages, related groups and compatibility clarification. Reports are
local and not pushed; issue bodies embed evidence/acceptance so they are reviewable now.

## Every finding issue

| Finding | Weaver | Priority | Primary group | Individual issue | Other group references |
|---|---|---|---|---|
| WV-EXAMPLE-001 | example | P1 | [#148](https://github.com/rafaelmdc/braidworks/issues/148) | [#174](https://github.com/rafaelmdc/braidworks/issues/174) | — |
| WV-EXAMPLE-002 | example | P2 | [#149](https://github.com/rafaelmdc/braidworks/issues/149) | [#175](https://github.com/rafaelmdc/braidworks/issues/175) | — |
| WV-EXAMPLE-003 | example | P2 | [#157](https://github.com/rafaelmdc/braidworks/issues/157) | [#176](https://github.com/rafaelmdc/braidworks/issues/176) | — |
| WV-EXAMPLE-004 | example | P2 | [#157](https://github.com/rafaelmdc/braidworks/issues/157) | [#177](https://github.com/rafaelmdc/braidworks/issues/177) | — |
| WV-EXAMPLE-005 | example | P2 | [#157](https://github.com/rafaelmdc/braidworks/issues/157) | [#178](https://github.com/rafaelmdc/braidworks/issues/178) | — |
| WV-EXAMPLE-006 | example | P3 | [#157](https://github.com/rafaelmdc/braidworks/issues/157) | [#179](https://github.com/rafaelmdc/braidworks/issues/179) | [#156](https://github.com/rafaelmdc/braidworks/issues/156) |
| WV-UNIPROT-001 | uniprot | P1 | [#155](https://github.com/rafaelmdc/braidworks/issues/155) | [#180](https://github.com/rafaelmdc/braidworks/issues/180) | — |
| WV-UNIPROT-002 | uniprot | P1 | [#155](https://github.com/rafaelmdc/braidworks/issues/155) | [#181](https://github.com/rafaelmdc/braidworks/issues/181) | — |
| WV-UNIPROT-003 | uniprot | P1 | [#151](https://github.com/rafaelmdc/braidworks/issues/151) | [#182](https://github.com/rafaelmdc/braidworks/issues/182) | — |
| WV-UNIPROT-004 | uniprot | P1 | [#150](https://github.com/rafaelmdc/braidworks/issues/150) | [#183](https://github.com/rafaelmdc/braidworks/issues/183) | — |
| WV-UNIPROT-005 | uniprot | P2 | [#150](https://github.com/rafaelmdc/braidworks/issues/150) | [#184](https://github.com/rafaelmdc/braidworks/issues/184) | — |
| WV-UNIPROT-006 | uniprot | P2 | [#149](https://github.com/rafaelmdc/braidworks/issues/149) | [#185](https://github.com/rafaelmdc/braidworks/issues/185) | [#154](https://github.com/rafaelmdc/braidworks/issues/154) |
| WV-UNIPROT-007 | uniprot | P2 | [#158](https://github.com/rafaelmdc/braidworks/issues/158) | [#186](https://github.com/rafaelmdc/braidworks/issues/186) | [#150](https://github.com/rafaelmdc/braidworks/issues/150), [#153](https://github.com/rafaelmdc/braidworks/issues/153), [#155](https://github.com/rafaelmdc/braidworks/issues/155), [#156](https://github.com/rafaelmdc/braidworks/issues/156) |
| WV-UNIPROT-008 | uniprot | P2 | [#148](https://github.com/rafaelmdc/braidworks/issues/148) | [#187](https://github.com/rafaelmdc/braidworks/issues/187) | — |
| WV-UNIPROT-009 | uniprot | P2 | [#158](https://github.com/rafaelmdc/braidworks/issues/158) | [#188](https://github.com/rafaelmdc/braidworks/issues/188) | — |
| WV-UNIPROT-010 | uniprot | P2 | [#158](https://github.com/rafaelmdc/braidworks/issues/158) | [#189](https://github.com/rafaelmdc/braidworks/issues/189) | [#155](https://github.com/rafaelmdc/braidworks/issues/155) |
| WV-PDBE-001 | pdbe | P1 | [#154](https://github.com/rafaelmdc/braidworks/issues/154) | [#190](https://github.com/rafaelmdc/braidworks/issues/190) | — |
| WV-PDBE-002 | pdbe | P1 | [#150](https://github.com/rafaelmdc/braidworks/issues/150) | [#191](https://github.com/rafaelmdc/braidworks/issues/191) | — |
| WV-PDBE-003 | pdbe | P2 | [#150](https://github.com/rafaelmdc/braidworks/issues/150) | [#192](https://github.com/rafaelmdc/braidworks/issues/192) | — |
| WV-PDBE-004 | pdbe | P2 | [#159](https://github.com/rafaelmdc/braidworks/issues/159) | [#193](https://github.com/rafaelmdc/braidworks/issues/193) | — |
| WV-PDBE-005 | pdbe | P2 | [#149](https://github.com/rafaelmdc/braidworks/issues/149) | [#194](https://github.com/rafaelmdc/braidworks/issues/194) | [#148](https://github.com/rafaelmdc/braidworks/issues/148) |
| WV-PDBE-006 | pdbe | P2 | [#159](https://github.com/rafaelmdc/braidworks/issues/159) | [#195](https://github.com/rafaelmdc/braidworks/issues/195) | — |
| WV-PDBE-007 | pdbe | P2 | [#155](https://github.com/rafaelmdc/braidworks/issues/155) | [#196](https://github.com/rafaelmdc/braidworks/issues/196) | — |
| WV-ALPHAFOLD-001 | alphafold | P1 | [#160](https://github.com/rafaelmdc/braidworks/issues/160) | [#197](https://github.com/rafaelmdc/braidworks/issues/197) | — |
| WV-ALPHAFOLD-002 | alphafold | P1 | [#150](https://github.com/rafaelmdc/braidworks/issues/150) | [#198](https://github.com/rafaelmdc/braidworks/issues/198) | — |
| WV-ALPHAFOLD-003 | alphafold | P2 | [#160](https://github.com/rafaelmdc/braidworks/issues/160) | [#199](https://github.com/rafaelmdc/braidworks/issues/199) | — |
| WV-ALPHAFOLD-004 | alphafold | P2 | [#149](https://github.com/rafaelmdc/braidworks/issues/149) | [#200](https://github.com/rafaelmdc/braidworks/issues/200) | [#154](https://github.com/rafaelmdc/braidworks/issues/154) |
| WV-ALPHAFOLD-005 | alphafold | P2 | [#148](https://github.com/rafaelmdc/braidworks/issues/148) | [#201](https://github.com/rafaelmdc/braidworks/issues/201) | — |
| WV-ALPHAFOLD-006 | alphafold | P2 | [#160](https://github.com/rafaelmdc/braidworks/issues/160) | [#202](https://github.com/rafaelmdc/braidworks/issues/202) | — |
| WV-QUICKGO-001 | quickgo | P1 | [#155](https://github.com/rafaelmdc/braidworks/issues/155) | [#203](https://github.com/rafaelmdc/braidworks/issues/203) | — |
| WV-QUICKGO-002 | quickgo | P1 | [#154](https://github.com/rafaelmdc/braidworks/issues/154) | [#204](https://github.com/rafaelmdc/braidworks/issues/204) | — |
| WV-QUICKGO-003 | quickgo | P1 | [#150](https://github.com/rafaelmdc/braidworks/issues/150) | [#205](https://github.com/rafaelmdc/braidworks/issues/205) | — |
| WV-QUICKGO-004 | quickgo | P2 | [#161](https://github.com/rafaelmdc/braidworks/issues/161) | [#206](https://github.com/rafaelmdc/braidworks/issues/206) | — |
| WV-QUICKGO-005 | quickgo | P2 | [#161](https://github.com/rafaelmdc/braidworks/issues/161) | [#207](https://github.com/rafaelmdc/braidworks/issues/207) | — |
| WV-QUICKGO-006 | quickgo | P2 | [#149](https://github.com/rafaelmdc/braidworks/issues/149) | [#208](https://github.com/rafaelmdc/braidworks/issues/208) | [#148](https://github.com/rafaelmdc/braidworks/issues/148) |
| WV-REACTOME-001 | reactome | P1 | [#154](https://github.com/rafaelmdc/braidworks/issues/154) | [#209](https://github.com/rafaelmdc/braidworks/issues/209) | — |
| WV-REACTOME-002 | reactome | P1 | [#150](https://github.com/rafaelmdc/braidworks/issues/150) | [#210](https://github.com/rafaelmdc/braidworks/issues/210) | — |
| WV-REACTOME-003 | reactome | P2 | [#150](https://github.com/rafaelmdc/braidworks/issues/150) | [#211](https://github.com/rafaelmdc/braidworks/issues/211) | — |
| WV-REACTOME-004 | reactome | P2 | [#162](https://github.com/rafaelmdc/braidworks/issues/162) | [#212](https://github.com/rafaelmdc/braidworks/issues/212) | — |
| WV-REACTOME-005 | reactome | P2 | [#149](https://github.com/rafaelmdc/braidworks/issues/149) | [#213](https://github.com/rafaelmdc/braidworks/issues/213) | [#148](https://github.com/rafaelmdc/braidworks/issues/148) |
| WV-REACTOME-006 | reactome | P2 | [#162](https://github.com/rafaelmdc/braidworks/issues/162) | [#214](https://github.com/rafaelmdc/braidworks/issues/214) | [#155](https://github.com/rafaelmdc/braidworks/issues/155) |
| WV-STRING-001 | string | P1 | [#155](https://github.com/rafaelmdc/braidworks/issues/155) | [#215](https://github.com/rafaelmdc/braidworks/issues/215) | — |
| WV-STRING-002 | string | P1 | [#151](https://github.com/rafaelmdc/braidworks/issues/151) | [#216](https://github.com/rafaelmdc/braidworks/issues/216) | — |
| WV-STRING-003 | string | P1 | [#155](https://github.com/rafaelmdc/braidworks/issues/155) | [#217](https://github.com/rafaelmdc/braidworks/issues/217) | — |
| WV-STRING-004 | string | P1 | [#154](https://github.com/rafaelmdc/braidworks/issues/154) | [#218](https://github.com/rafaelmdc/braidworks/issues/218) | — |
| WV-STRING-005 | string | P2 | [#163](https://github.com/rafaelmdc/braidworks/issues/163) | [#219](https://github.com/rafaelmdc/braidworks/issues/219) | — |
| WV-STRING-006 | string | P2 | [#150](https://github.com/rafaelmdc/braidworks/issues/150) | [#220](https://github.com/rafaelmdc/braidworks/issues/220) | — |
| WV-STRING-007 | string | P2 | [#163](https://github.com/rafaelmdc/braidworks/issues/163) | [#221](https://github.com/rafaelmdc/braidworks/issues/221) | [#148](https://github.com/rafaelmdc/braidworks/issues/148), [#149](https://github.com/rafaelmdc/braidworks/issues/149), [#153](https://github.com/rafaelmdc/braidworks/issues/153) |
| WV-NCBI-001 | ncbi | P0 | [#152](https://github.com/rafaelmdc/braidworks/issues/152) | [#222](https://github.com/rafaelmdc/braidworks/issues/222) | — |
| WV-NCBI-002 | ncbi | P1 | [#164](https://github.com/rafaelmdc/braidworks/issues/164) | [#223](https://github.com/rafaelmdc/braidworks/issues/223) | — |
| WV-NCBI-003 | ncbi | P1 | [#151](https://github.com/rafaelmdc/braidworks/issues/151) | [#224](https://github.com/rafaelmdc/braidworks/issues/224) | — |
| WV-NCBI-004 | ncbi | P1 | [#155](https://github.com/rafaelmdc/braidworks/issues/155) | [#225](https://github.com/rafaelmdc/braidworks/issues/225) | — |
| WV-NCBI-005 | ncbi | P1 | [#150](https://github.com/rafaelmdc/braidworks/issues/150) | [#226](https://github.com/rafaelmdc/braidworks/issues/226) | — |
| WV-NCBI-006 | ncbi | P2 | [#149](https://github.com/rafaelmdc/braidworks/issues/149) | [#227](https://github.com/rafaelmdc/braidworks/issues/227) | [#154](https://github.com/rafaelmdc/braidworks/issues/154) |
| WV-NCBI-007 | ncbi | P2 | [#153](https://github.com/rafaelmdc/braidworks/issues/153) | [#228](https://github.com/rafaelmdc/braidworks/issues/228) | — |
| WV-NCBI-008 | ncbi | P2 | [#151](https://github.com/rafaelmdc/braidworks/issues/151) | [#229](https://github.com/rafaelmdc/braidworks/issues/229) | — |
| WV-NCBI-009 | ncbi | P2 | [#164](https://github.com/rafaelmdc/braidworks/issues/164) | [#230](https://github.com/rafaelmdc/braidworks/issues/230) | — |
| WV-NCBI-010 | ncbi | P2 | [#164](https://github.com/rafaelmdc/braidworks/issues/164) | [#231](https://github.com/rafaelmdc/braidworks/issues/231) | — |
| WV-GTDB-001 | gtdb | P1 | [#155](https://github.com/rafaelmdc/braidworks/issues/155) | [#232](https://github.com/rafaelmdc/braidworks/issues/232) | — |
| WV-GTDB-002 | gtdb | P1 | [#155](https://github.com/rafaelmdc/braidworks/issues/155) | [#233](https://github.com/rafaelmdc/braidworks/issues/233) | — |
| WV-GTDB-003 | gtdb | P1 | [#165](https://github.com/rafaelmdc/braidworks/issues/165) | [#234](https://github.com/rafaelmdc/braidworks/issues/234) | [#155](https://github.com/rafaelmdc/braidworks/issues/155) |
| WV-GTDB-004 | gtdb | P1 | [#154](https://github.com/rafaelmdc/braidworks/issues/154) | [#235](https://github.com/rafaelmdc/braidworks/issues/235) | — |
| WV-GTDB-005 | gtdb | P2 | [#152](https://github.com/rafaelmdc/braidworks/issues/152) | [#236](https://github.com/rafaelmdc/braidworks/issues/236) | — |
| WV-GTDB-006 | gtdb | P2 | [#165](https://github.com/rafaelmdc/braidworks/issues/165) | [#237](https://github.com/rafaelmdc/braidworks/issues/237) | [#150](https://github.com/rafaelmdc/braidworks/issues/150) |
| WV-GTDB-007 | gtdb | P2 | [#156](https://github.com/rafaelmdc/braidworks/issues/156) | [#238](https://github.com/rafaelmdc/braidworks/issues/238) | — |
| WV-GTDB-008 | gtdb | P2 | [#149](https://github.com/rafaelmdc/braidworks/issues/149) | [#239](https://github.com/rafaelmdc/braidworks/issues/239) | [#153](https://github.com/rafaelmdc/braidworks/issues/153), [#154](https://github.com/rafaelmdc/braidworks/issues/154) |
| WV-GTDB-009 | gtdb | P2 | [#165](https://github.com/rafaelmdc/braidworks/issues/165) | [#240](https://github.com/rafaelmdc/braidworks/issues/240) | [#148](https://github.com/rafaelmdc/braidworks/issues/148) |
| WV-BACDIVE-001 | bacdive | P1 | [#155](https://github.com/rafaelmdc/braidworks/issues/155) | [#241](https://github.com/rafaelmdc/braidworks/issues/241) | — |
| WV-BACDIVE-002 | bacdive | P1 | [#151](https://github.com/rafaelmdc/braidworks/issues/151) | [#242](https://github.com/rafaelmdc/braidworks/issues/242) | [#154](https://github.com/rafaelmdc/braidworks/issues/154) |
| WV-BACDIVE-003 | bacdive | P1 | [#150](https://github.com/rafaelmdc/braidworks/issues/150) | [#243](https://github.com/rafaelmdc/braidworks/issues/243) | — |
| WV-BACDIVE-004 | bacdive | P2 | [#153](https://github.com/rafaelmdc/braidworks/issues/153) | [#244](https://github.com/rafaelmdc/braidworks/issues/244) | [#156](https://github.com/rafaelmdc/braidworks/issues/156) |
| WV-BACDIVE-005 | bacdive | P2 | [#155](https://github.com/rafaelmdc/braidworks/issues/155) | [#245](https://github.com/rafaelmdc/braidworks/issues/245) | — |
| WV-BACDIVE-006 | bacdive | P2 | [#166](https://github.com/rafaelmdc/braidworks/issues/166) | [#246](https://github.com/rafaelmdc/braidworks/issues/246) | — |
| WV-BACDIVE-007 | bacdive | P2 | [#149](https://github.com/rafaelmdc/braidworks/issues/149) | [#247](https://github.com/rafaelmdc/braidworks/issues/247) | [#148](https://github.com/rafaelmdc/braidworks/issues/148), [#154](https://github.com/rafaelmdc/braidworks/issues/154) |
| WV-AGORA-001 | agora | P1 | [#151](https://github.com/rafaelmdc/braidworks/issues/151) | [#248](https://github.com/rafaelmdc/braidworks/issues/248) | — |
| WV-AGORA-002 | agora | P1 | [#167](https://github.com/rafaelmdc/braidworks/issues/167) | [#249](https://github.com/rafaelmdc/braidworks/issues/249) | [#150](https://github.com/rafaelmdc/braidworks/issues/150), [#151](https://github.com/rafaelmdc/braidworks/issues/151), [#152](https://github.com/rafaelmdc/braidworks/issues/152), [#154](https://github.com/rafaelmdc/braidworks/issues/154) |
| WV-AGORA-003 | agora | P2 | [#151](https://github.com/rafaelmdc/braidworks/issues/151) | [#250](https://github.com/rafaelmdc/braidworks/issues/250) | — |
| WV-AGORA-004 | agora | P2 | [#167](https://github.com/rafaelmdc/braidworks/issues/167) | [#251](https://github.com/rafaelmdc/braidworks/issues/251) | — |
| WV-AGORA-005 | agora | P2 | [#152](https://github.com/rafaelmdc/braidworks/issues/152) | [#252](https://github.com/rafaelmdc/braidworks/issues/252) | [#154](https://github.com/rafaelmdc/braidworks/issues/154) |
| WV-AGORA-006 | agora | P2 | [#149](https://github.com/rafaelmdc/braidworks/issues/149) | [#253](https://github.com/rafaelmdc/braidworks/issues/253) | [#148](https://github.com/rafaelmdc/braidworks/issues/148) |
| WV-AGORA-008 | agora | P2 | [#167](https://github.com/rafaelmdc/braidworks/issues/167) | [#254](https://github.com/rafaelmdc/braidworks/issues/254) | — |
| WV-AGORA-007 | agora | P3 | [#156](https://github.com/rafaelmdc/braidworks/issues/156) | [#255](https://github.com/rafaelmdc/braidworks/issues/255) | — |
| WV-FAPROTAX-001 | faprotax | P1 | [#168](https://github.com/rafaelmdc/braidworks/issues/168) | [#256](https://github.com/rafaelmdc/braidworks/issues/256) | [#155](https://github.com/rafaelmdc/braidworks/issues/155) |
| WV-FAPROTAX-002 | faprotax | P1 | [#168](https://github.com/rafaelmdc/braidworks/issues/168) | [#257](https://github.com/rafaelmdc/braidworks/issues/257) | — |
| WV-FAPROTAX-003 | faprotax | P2 | [#168](https://github.com/rafaelmdc/braidworks/issues/168) | [#258](https://github.com/rafaelmdc/braidworks/issues/258) | [#150](https://github.com/rafaelmdc/braidworks/issues/150) |
| WV-FAPROTAX-004 | faprotax | P2 | [#168](https://github.com/rafaelmdc/braidworks/issues/168) | [#259](https://github.com/rafaelmdc/braidworks/issues/259) | — |
| WV-FAPROTAX-005 | faprotax | P2 | [#149](https://github.com/rafaelmdc/braidworks/issues/149) | [#260](https://github.com/rafaelmdc/braidworks/issues/260) | [#148](https://github.com/rafaelmdc/braidworks/issues/148) |
| WV-FAPROTAX-006 | faprotax | P3 | [#156](https://github.com/rafaelmdc/braidworks/issues/156) | [#261](https://github.com/rafaelmdc/braidworks/issues/261) | — |
| WV-DISBIOME-001 | disbiome | P1 | [#169](https://github.com/rafaelmdc/braidworks/issues/169) | [#262](https://github.com/rafaelmdc/braidworks/issues/262) | [#155](https://github.com/rafaelmdc/braidworks/issues/155) |
| WV-DISBIOME-002 | disbiome | P2 | [#156](https://github.com/rafaelmdc/braidworks/issues/156) | [#263](https://github.com/rafaelmdc/braidworks/issues/263) | — |
| WV-DISBIOME-003 | disbiome | P2 | [#169](https://github.com/rafaelmdc/braidworks/issues/169) | [#264](https://github.com/rafaelmdc/braidworks/issues/264) | — |
| WV-DISBIOME-004 | disbiome | P2 | [#169](https://github.com/rafaelmdc/braidworks/issues/169) | [#265](https://github.com/rafaelmdc/braidworks/issues/265) | [#150](https://github.com/rafaelmdc/braidworks/issues/150), [#151](https://github.com/rafaelmdc/braidworks/issues/151) |
| WV-DISBIOME-005 | disbiome | P2 | [#149](https://github.com/rafaelmdc/braidworks/issues/149) | [#266](https://github.com/rafaelmdc/braidworks/issues/266) | [#148](https://github.com/rafaelmdc/braidworks/issues/148) |
| WV-DISBIOME-006 | disbiome | P3 | [#156](https://github.com/rafaelmdc/braidworks/issues/156) | [#267](https://github.com/rafaelmdc/braidworks/issues/267) | — |
| WV-GMREPO-001 | gmrepo | P1 | [#151](https://github.com/rafaelmdc/braidworks/issues/151) | [#268](https://github.com/rafaelmdc/braidworks/issues/268) | [#150](https://github.com/rafaelmdc/braidworks/issues/150) |
| WV-GMREPO-002 | gmrepo | P1 | [#151](https://github.com/rafaelmdc/braidworks/issues/151) | [#269](https://github.com/rafaelmdc/braidworks/issues/269) | — |
| WV-GMREPO-003 | gmrepo | P2 | [#155](https://github.com/rafaelmdc/braidworks/issues/155) | [#270](https://github.com/rafaelmdc/braidworks/issues/270) | [#153](https://github.com/rafaelmdc/braidworks/issues/153) |
| WV-GMREPO-004 | gmrepo | P2 | [#170](https://github.com/rafaelmdc/braidworks/issues/170) | [#271](https://github.com/rafaelmdc/braidworks/issues/271) | [#150](https://github.com/rafaelmdc/braidworks/issues/150) |
| WV-GMREPO-005 | gmrepo | P2 | [#170](https://github.com/rafaelmdc/braidworks/issues/170) | [#272](https://github.com/rafaelmdc/braidworks/issues/272) | — |
| WV-GMREPO-006 | gmrepo | P2 | [#153](https://github.com/rafaelmdc/braidworks/issues/153) | [#273](https://github.com/rafaelmdc/braidworks/issues/273) | [#151](https://github.com/rafaelmdc/braidworks/issues/151) |
| WV-GMREPO-007 | gmrepo | P2 | [#149](https://github.com/rafaelmdc/braidworks/issues/149) | [#274](https://github.com/rafaelmdc/braidworks/issues/274) | [#148](https://github.com/rafaelmdc/braidworks/issues/148), [#156](https://github.com/rafaelmdc/braidworks/issues/156) |
| WV-MONDO-001 | mondo | P1 | [#155](https://github.com/rafaelmdc/braidworks/issues/155) | [#275](https://github.com/rafaelmdc/braidworks/issues/275) | — |
| WV-MONDO-002 | mondo | P1 | [#155](https://github.com/rafaelmdc/braidworks/issues/155) | [#276](https://github.com/rafaelmdc/braidworks/issues/276) | — |
| WV-MONDO-003 | mondo | P1 | [#171](https://github.com/rafaelmdc/braidworks/issues/171) | [#277](https://github.com/rafaelmdc/braidworks/issues/277) | — |
| WV-MONDO-004 | mondo | P2 | [#171](https://github.com/rafaelmdc/braidworks/issues/171) | [#278](https://github.com/rafaelmdc/braidworks/issues/278) | — |
| WV-MONDO-005 | mondo | P2 | [#156](https://github.com/rafaelmdc/braidworks/issues/156) | [#279](https://github.com/rafaelmdc/braidworks/issues/279) | — |
| WV-MONDO-006 | mondo | P2 | [#154](https://github.com/rafaelmdc/braidworks/issues/154) | [#280](https://github.com/rafaelmdc/braidworks/issues/280) | — |
| WV-MONDO-007 | mondo | P2 | [#149](https://github.com/rafaelmdc/braidworks/issues/149) | [#281](https://github.com/rafaelmdc/braidworks/issues/281) | [#148](https://github.com/rafaelmdc/braidworks/issues/148) |
| WV-WIKIDATA-001 | wikidata | P1 | [#150](https://github.com/rafaelmdc/braidworks/issues/150) | [#282](https://github.com/rafaelmdc/braidworks/issues/282) | — |
| WV-WIKIDATA-002 | wikidata | P2 | [#150](https://github.com/rafaelmdc/braidworks/issues/150) | [#283](https://github.com/rafaelmdc/braidworks/issues/283) | — |
| WV-WIKIDATA-003 | wikidata | P2 | [#155](https://github.com/rafaelmdc/braidworks/issues/155) | [#284](https://github.com/rafaelmdc/braidworks/issues/284) | — |
| WV-WIKIDATA-004 | wikidata | P2 | [#149](https://github.com/rafaelmdc/braidworks/issues/149) | [#285](https://github.com/rafaelmdc/braidworks/issues/285) | [#154](https://github.com/rafaelmdc/braidworks/issues/154) |
| WV-WIKIDATA-005 | wikidata | P2 | [#172](https://github.com/rafaelmdc/braidworks/issues/172) | [#286](https://github.com/rafaelmdc/braidworks/issues/286) | — |
| WV-WIKIDATA-006 | wikidata | P2 | [#150](https://github.com/rafaelmdc/braidworks/issues/150) | [#287](https://github.com/rafaelmdc/braidworks/issues/287) | — |
| WV-WIKIDATA-007 | wikidata | P2 | [#148](https://github.com/rafaelmdc/braidworks/issues/148) | [#288](https://github.com/rafaelmdc/braidworks/issues/288) | — |
| WV-WIKIPEDIA-001 | wikipedia | P1 | [#151](https://github.com/rafaelmdc/braidworks/issues/151) | [#289](https://github.com/rafaelmdc/braidworks/issues/289) | [#154](https://github.com/rafaelmdc/braidworks/issues/154) |
| WV-WIKIPEDIA-002 | wikipedia | P1 | [#151](https://github.com/rafaelmdc/braidworks/issues/151) | [#290](https://github.com/rafaelmdc/braidworks/issues/290) | — |
| WV-WIKIPEDIA-003 | wikipedia | P1 | [#154](https://github.com/rafaelmdc/braidworks/issues/154) | [#291](https://github.com/rafaelmdc/braidworks/issues/291) | — |
| WV-WIKIPEDIA-004 | wikipedia | P1 | [#150](https://github.com/rafaelmdc/braidworks/issues/150) | [#292](https://github.com/rafaelmdc/braidworks/issues/292) | — |
| WV-WIKIPEDIA-005 | wikipedia | P2 | [#149](https://github.com/rafaelmdc/braidworks/issues/149) | [#293](https://github.com/rafaelmdc/braidworks/issues/293) | [#153](https://github.com/rafaelmdc/braidworks/issues/153), [#154](https://github.com/rafaelmdc/braidworks/issues/154) |
| WV-WIKIPEDIA-006 | wikipedia | P2 | [#154](https://github.com/rafaelmdc/braidworks/issues/154) | [#294](https://github.com/rafaelmdc/braidworks/issues/294) | [#151](https://github.com/rafaelmdc/braidworks/issues/151) |
| WV-WIKIPEDIA-007 | wikipedia | P2 | [#173](https://github.com/rafaelmdc/braidworks/issues/173) | [#295](https://github.com/rafaelmdc/braidworks/issues/295) | [#148](https://github.com/rafaelmdc/braidworks/issues/148), [#151](https://github.com/rafaelmdc/braidworks/issues/151) |

## Verification

Verified all 26 native group parents under #147 and all 122 native finding-parent
relationships by listing the actual GitHub sub-issues and comparing exact child IDs.
Unique finding IDs, single primary ownership and 122 source spec/work-package references
were checked before creation. The mapping includes cross-links for mixed concerns.
Eight offline reproductions passed execution again; these are evidence scripts, not
tests proving behavior is correct. No production source changes, push, tags or publishing.
