# faprotax_weaver

Match an organism lineage to putative ecological functions in bundled FAPROTAX rules, then
inspect the supporting membership trace. NCBI can supply the lineage from an organism name.
These are taxonomy-based affiliations, not measured functions of every strain; an empty match
does not establish functional absence.

- **Source:** https://pages.uoregon.edu/slouca/LoucaLab/archive/FAPROTAX/
- **License:** Open
- **Cite:** https://doi.org/10.1126/science.aaf4507

## Capabilities

| Capability | Use it to |
|---|---|
| `describe_ecology` | Retrieve functional affiliations and optional rule evidence |

See [source reference](REFERENCE.md#capabilities) for exact inputs, output groups, backends and parameters,
or inspect the [spec](weaver.spec.toml).

## Licensing & attribution

FAPROTAX is distributed under a **custom BSD-3-Clause-style license** (© Stilianos
Louca); redistributions must retain its copyright notice and disclaimer, and any
modification must be clearly indicated. The bundled `FAPROTAX.txt` is included
**verbatim and unmodified**, so its embedded license header satisfies the notice
requirement. It is recorded in the spec as `license = "Open"` (nearest known
identifier) with citation and attribution.

- **Cite:** Louca, Parfrey & Doebeli (2016), *Science* — https://doi.org/10.1126/science.aaf4507
- **Database:** © Stilianos Louca — https://pages.uoregon.edu/slouca/LoucaLab/archive/FAPROTAX/

## Run a lineage-based query

```bash
braidworks weave --have organism.name=Methylococcus --want microbe.ecology.functional_groups --policy api_first
```

This routes through NCBI to obtain the structured lineage (network access
required), then matches bundled FAPROTAX rules locally. The CLI’s table/scalar
input format does not directly represent a lineage list; use Python for direct
structured lineage calls. Affiliation is a putative taxonomy-based inference,
not proof of function in each strain.

Follow the [researcher lesson](../../docs/tutorials/microbial-functions.md) for a complete exercise.

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
