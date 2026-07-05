# agora_weaver

AGORA2 metabolic reconstructions (NCBI taxid -> reconstruction + reaction repertoire) weaver for Braidworks.

- **Source:** [Virtual Metabolic Human (VMH)](https://www.vmh.life) — AGORA2 (Heinken et al., *Nat Biotechnol* 2023)
- **License:** **CC BY-NC 4.0** ⚠️ — the VMH/AGORA2 *data* is **NonCommercial**. Fine for
  research/academic use; commercial use needs permission from the VMH authors. (The AGORA2
  *pipeline code* on GitHub is MIT, but that does not relax the data terms.)
- **Attribution:** AGORA2 / Virtual Metabolic Human (VMH), Heinken et al.
- **Cite:** https://doi.org/10.1038/s41587-022-01628-0

Maps an organism (by **NCBI taxid**) to its AGORA2 genome-scale metabolic
reconstruction(s) and, on request, the **reaction repertoire** of those models — the
substrate for metabolic complementarity/competition analysis. Consumes only `ncbi.taxon.id`
(name→taxid is `ncbi_weaver`'s job; the braider chains them).

## Outputs (grouped)

- **`core`** → `microbe.metabolism.reconstruction`: a list of `{reconstruction_id, gcf_id}`
  (the AGORA2 model and the RefSeq genome it was built from). Served from a **bundled**
  crosswalk (AGORA2 Supplementary Table S1) — **offline, all 7,302 strains, no download.**
- **`reactions`** → `microbe.metabolism.reactions`: the per-model reaction repertoire, a
  list of `{reconstruction_id, abbreviation, subsystem, ec, kegg, rhea}` (EC/KEGG/Rhea from
  the VMH reaction crosswalk — so this also acts as an **intermediate** into the molecular
  hub). Needs the reaction DB built by `ensure_agora_db` from the AGORA2 SBML archive
  (~2.17 GB, consent-gated); absent it, `core` still answers.

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

A weaver is only reachable to the braider once its provider is registered in the
application's `WeaverFactory`. Wherever you assemble the factory:

```python
from braidworks.core import WeaverFactory
import agora_weaver

factory = WeaverFactory()
agora_weaver.register(factory)        # makes "agora" buildable
```
