# AlphaFold weaver audit

Date 2026-10-08; revision `d5e7543`; package `0.1.6`, core floor `0.13.0`.
Status audited locally; no implementation changes.

## Findings

| ID | Priority/confidence | Finding/evidence | Action |
|---|---|---|---|
| WV-ALPHAFOLD-001 | P1 verified | F1 selected as canonical full model, but F1 also identifies first overlapping fragment for long proteins; extracted records omit start/end coverage | Preserve model coverage/fragment identity and explicitly warn/document partial representative coverage |
| WV-ALPHAFOLD-002 | P1 verified | Invalid JSON escapes; wrong response object becomes NO_MATCH; null list members would fail `_pick` | Validate expected list/entry shape and report source failure values |
| WV-ALPHAFOLD-003 | P2 verified | PAE is only image URL; per-residue confidence, PAE JSON URL and sequence coverage absent | Optional confidence/coverage fields and downloadable raw-data references; avoid eager large matrix downloads |
| WV-ALPHAFOLD-004 | P2 verified | Builder ignores config; owned client never closed; endpoint omitted from static fingerprint | Reference shared construction/lifecycle/source-identity policy WV-UNIPROT-006 |
| WV-ALPHAFOLD-005 | P2 verified | README claims near-universal availability for well-formed accessions and universal same-accession same-model; contributor regeneration guidance stale | Document exclusions/version changes and selection policy; reference WV-EXAMPLE-001 |
| WV-ALPHAFOLD-006 | P2 supported inference | Only one selected record exposed when API returns multiple models; isoform/fragment exploration unavailable | Evaluate list_models plus entry-specific describe, preserving current representative capability |

001 reproduces loss of start/end in a two-fragment fixture and is supported by official
download documentation. It does not claim the small P04637 model is fragmented.

## Research and workflow coverage

Primary sources accessed 2026-10-08:
[official FAQ](https://alphafold.ebi.ac.uk/faq),
[downloads/fragment explanation](https://www.alphafold.ebi.ac.uk/download),
[confidence training](https://www.ebi.ac.uk/training/online/courses/alphafold/inputs-and-outputs/evaluating-alphafolds-predicted-structures-using-confidence-scores/),
[model-page training](https://www.ebi.ac.uk/training/online/courses/navigating-alphafold-database/understanding-the-structure-prediction-page/summary-and-model-confidence-tab/).
Official explanations differ by dataset on length cutoffs, so do not hardcode one
universal threshold; derive coverage from actual model metadata.

| Workflow | Current support | Gap/action |
|---|---|---|
| Retrieve predicted coordinates for an identified protein | Partial: selected PDB URL/version, CIF URL in detail | Preserve represented sequence range and all relevant fragments |
| Assess local reliability/disordered regions before structural interpretation | Partial: mean pLDDT and fractions | Mean is insufficient for residue-specific assertions; offer raw confidence reference/coverage |
| Assess inter-domain orientation with PAE | Partial: PAE image URL | Structured PAE download reference, explanatory units/limits; no automatic matrix computation |
| Compare isoforms or long-protein fragment models | Absent as a complete model list | Conditional list/describe pair |

These are demonstrated provider learning tasks, not quantified popularity claims.
Existing API concerns database retrieval; submitting AlphaFold jobs/complex modeling
is a different service and remains out of scope.

## Capability and checklist

`describe_model`, API-only, consumes UniProt accession, max batch25; model and full
groups expose selected entry ID, mean pLDDT, PDB/PAE-image URLs, latest version and
summary record. No declared parameters, no set output/model-entry consumer.

- **Correctness:** F1 canonical preference works for observed P04637 isoforms; lexical
  fallback is selection policy, not proof of biologically appropriate completeness.
  pLDDT is local model confidence on 0–100, not experimental validation or probability
  of protein identity. Core strand confidence remains default1, a different concept.
- **OOP/functional design:** thin shared dispatch plus injected backend already fits.
  `_pick`/`_extract` are useful pure functions. Make selection an explicit pure policy
  taking validated entries; strategy classes only if distinct caller policies emerge.
  No new template hierarchy or repository warranted for one read endpoint.
- **Backend:** bounded concurrency4, pacing, 400/404 misses and HTTP failures as values;
  no schema boundary, retries or lifecycle closing. Null input becomes string None
  rather than blank; validate input normalization consistently.
- **Build/local parity:** no local build/DB/backend; bundled mock fixture only.
  Source API contract fingerprint is not frozen-data provenance; record model version
  and creation/sequence dates where useful. No bulk model-file downloads required.
- **Connectivity:** accession consumer is useful; introducing model entry fan-out
  requires registered bridge key and explicit limits. Current leaf outputs suffice
  for a basic dossier, not residue analysis.
- **Docs/usability:** CLI retrieval examples exist; Python only constructs. Current
  docs overstate coverage and determinism; source licenses/citation present.
- **Tests:** canonical/isoform selection and concurrency/order covered; two live tests
  do not cover long fragments, sparse invalid entries or confidence download metadata.
  Add meaningful source-shape and fragment cases, retaining strict/conformance.

## Evidence

**27 passed, 2 skipped**; strict fixture verification passed. Invalid JSON raised
JSONDecodeError; wrong-shape object produced NO_MATCH. Two-fragment pure probe chose
`AF-Q8WZ42-F1` but `_extract` lost uniprotStart/uniprotEnd. Live
`/api/prediction/P04637` returned 200 and nine entries: canonical plus eight isoforms,
all latestVersion6; canonical range1–393. This is a small observed schema check,
not a full live suite or a probe of every long-protein endpoint.

Evidence: [backend](../../../weavers/alphafold_weaver/src/alphafold_weaver/backends/api.py),
[spec](../../../weavers/alphafold_weaver/weaver.spec.toml),
[tests](../../../weavers/alphafold_weaver/tests/test_api.py),
[README](../../../weavers/alphafold_weaver/README.md).
See [spec](alphafold.spec.md), [plan](alphafold.plan.md).
