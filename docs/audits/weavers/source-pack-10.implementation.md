# Source audit pack of 10

Local branch: `fix/source-audit-pack-10`. No push or release.

| Group | Completed original issues | Evidence | Remaining issues |
|---|---|---|---|
| AlphaFold #160 | #197 | [Coverage](SRC-ALPHAFOLD.implementation.md) | #199/#202 scope |
| Reactome #162 | #214 | [Listing evidence](SRC-REACTOME.implementation.md) | #212 scope |
| STRING #163 | #221 | [Source request policy](SRC-STRING.implementation.md) | #219 scope |
| NCBI #164 | #230 | [JSON/interfaces](SRC-NCBI.implementation.md) | #231 docs/features |
| AGORA #167 | #249/#254 | [Artifact safety/licenses](SRC-AGORA.implementation.md) | #251 scope; #298 source acquisition |
| FAPROTAX #168 | #256–#259 | [Rules and oracle](SRC-FAPROTAX.implementation.md) | #297 public evidence scope |

Repository lint/test pass: **2094 pytest cases + 5 tool unittest tests**,
56 opt-in skips. Strict verification passed for all six changed weavers.
FAPROTAX comparison: 25,068 cases, 92 groups, zero provider-reference differences.

Live evidence: AlphaFold 2 passed; STRING 3 passed; Reactome listing passed and 2
other cases skipped due to upstream transient failures. AGORA single-model test
failed: same-helper inspection confirmed HTML instead of SBML. Artifact validation
rejected it and published nothing; #298 tracks acquisition independently. Do not
interpret this as a successful live AGORA download.

[Decision stack](decision-stack.md) includes context/recommendations for scope choices.
Remaining correctness work can proceed independently, beginning with Disbiome build
integrity (#265), exact rank-aware input reachability (#262), and AGORA acquisition
research (#298). Mixed docs/feature findings can receive docs corrections first.

## Local commits

- `d515372` — core
- `5dd96bd` — alphafold
- `1ec829f` — reactome
- `e834a75` — string
- `5582f00` — ncbi
- `5b0c245` — agora
- `b7d1c6c` — faprotax
