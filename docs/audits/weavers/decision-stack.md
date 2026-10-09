# Weaver audit decision stack

Settled correctness and documentation issues proceed in batches. This stack collects scope/API choices for review after that work; it is not a claim that every other open issue needs a decision.

| Issue | Context | Recommendation | Decision needed |
|---|---|---|---|
| [#193](https://github.com/rafaelmdc/braidworks/issues/193) — PDBe mapping/quality | Original chain evidence is retained, but richer residue mapping and quality groups are new output scope with different upstream costs. Assembly and ligand records have different entity shapes. | Add stable normalized mapping and a separate quality group; treat assembly/ligand capabilities as separate future work. | Which new output scope should this round include? |
| [#234](https://github.com/rafaelmdc/braidworks/issues/234) — GTDB distance comparability | Current root paths contain node IDs and depths, without a tree/release identity. Summing depths across disconnected trees is not a scientifically defined patristic distance; paths from different releases can accidentally share node IDs. | Introduce a serializable path value carrying tree/release identity and reject incomparable paths explicitly. Update the dependent project rather than retain ambiguous numerical behavior. | Confirm the public path migration and how callers represent incomparable pairs. |

| [#199](https://github.com/rafaelmdc/braidworks/issues/199) — AlphaFold confidence | Existing output links a PAE image; machine-readable PAE and residue-confidence references would add useful analysis inputs. Large matrices need not be fetched during a lookup. | Add observed raw-data URLs and coverage/confidence metadata in a requested output group, with metric semantics documented. | Include these new references and fields in this round? |
| [#202](https://github.com/rafaelmdc/braidworks/issues/202) — AlphaFold model exploration | A representative lookup currently returns one model, so callers cannot explore all fragments or alternative models. Correcting representative coverage (#197) can proceed independently. | Add paired list_models/describe_model capabilities with stable model IDs and bounded fan-out. | Include the new capabilities now or defer them? |

Additional scope choices will be added as the remaining source issues are reviewed. Publishing and persistent cache/resume remain deferred (#142/#143).

## Completed correctness batch

#195, #277, #271 and #237 are closed with separate local commits. Workspace lint/test passed (2045 pytest cases, 56 skips, plus tool unittest checks); strict verification passed for the changed weavers. Next settled correction: AlphaFold #197. Thirty original source findings remain, plus the separately tracked optional #296; this stack is partial and will grow as scope choices are reviewed.
