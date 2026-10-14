# agora_weaver

Use AGORA2 to find metabolic reconstructions from taxids or genome accessions, then inspect
model reactions and source annotations. The bundled crosswalk works offline; reactions require
an acquired database, and model downloads require consent. Model membership is not measured
metabolic activity.

- **Source:** [Virtual Metabolic Human (VMH)](https://www.vmh.life) — AGORA2 (Heinken et al., *Nat Biotechnol* 2023)
- **License:** **CC BY-NC 4.0** ⚠️ — the VMH/AGORA2 *data* is **NonCommercial**. Fine for
  research/academic use; commercial use needs permission from the VMH authors. (The AGORA2
  *pipeline code* on GitHub is MIT, but that does not relax the data terms.)
- **Attribution:** AGORA2 / Virtual Metabolic Human (VMH), Heinken et al.
- **Cite:** https://doi.org/10.1038/s41587-022-01628-0

## Capabilities

| Capability | Use it to |
|---|---|
| `describe_metabolic_reconstruction` | Find reconstructions and optional reaction/model outputs for a taxid |
| `list_reconstructions` | Find reconstruction IDs from taxids or genome accessions |
| `describe_reconstruction` | Inspect one release-qualified reconstruction |
| `list_genomes` | List observed genome accessions for a reconstruction |
| `list_reactions` | List reactions for a reconstruction or pathway |
| `describe_reaction` | Inspect one source reaction |

See [source reference](REFERENCE.md#capabilities) for exact inputs, output groups, backends and parameters,
or inspect the [spec](weaver.spec.toml).

## Query the bundled crosswalk

With the package installed, run:

```bash
braidworks run agora describe_metabolic_reconstruction --have ncbi.taxon.id=562 \
    --want microbe.metabolism.reconstruction
```

The crosswalk works without acquiring models. Reaction and SBML outputs have separate
resource and consent requirements; follow [output/setup reference](REFERENCE.md#outputs-grouped)
before enabling acquisition. Archive acquisition can require multi-GB space.

## Setup, interpretation and contribution

Use [checkout or wheel installation](../../docs/installation.md) with core and the
sources needed for your route. From the checkout, prefix commands above with
`uv run --no-sync`; a bare command assumes the environment is activated.
Source installation does not acquire optional biological databases.

[Source reference](REFERENCE.md) retains coverage, selection, failure and resource
rules. [Builder configuration](../../docs/weaver-configuration.md) documents supported
options and ownership; close configured weavers after work completes. See
[contributing](CONTRIBUTING.md) to extend this source, and run package checks from
this package directory. Current installation does not assume package-index publication.

## Software license

The software uses [MIT](LICENSE). Provider data retain their source licenses and
attribution requirements above; the manifest data license does not license this code.
