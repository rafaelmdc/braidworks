# AlphaFold proposed specification

Status proposed. [Evidence](alphafold.audit.md).

| ID | Required behavior/acceptance |
|---|---|
| WV-ALPHAFOLD-001 | Selected model records retain range/length and distinguish partial fragments; fixture proves F1 alone is not represented as complete long-protein coverage. |
| WV-ALPHAFOLD-002 | Expected decoding/schema failures become ERROR, valid empty list is NO_MATCH; malformed member cannot abort unrelated input results. |
| WV-ALPHAFOLD-003 | Conditional confidence group exposes observed PAE JSON/confidence references and explains metric semantics; no eager matrix downloads. |
| WV-ALPHAFOLD-004 | Configured builder/lifecycle/source identity follows accepted shared policy; borrowed clients untouched. |
| WV-ALPHAFOLD-005 | Docs accurately distinguish isoforms/fragments, exclusions, latest-version retrieval and safe regeneration. |
| WV-ALPHAFOLD-006 | Conditional list/describe model contracts preserve all models with stable identity and bounded expansion; original representative capability retained. |

Keep current IDs/output types backward compatible. Features003/006 require scope
review. No AlphaFold job submission or complex-prediction engine. Patch all version
sites for behavior/manifest changes; do not regenerate over existing backend.
