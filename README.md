# Braidworks

Braidworks connects biological databases so you can go from *what you have* (a gene
name, an organism, a protein accession) to *what you want* (structures, pathways,
interactions, taxonomy, phenotypes) without hand-writing the glue between every API.

Each data source is wrapped in a **weaver** that declares, in typed terms, what it
*consumes* and *produces*. Braidworks reads those declarations, finds a route from
your inputs to your targets across all installed weavers, and runs it — in batch,
with caching, deduplication, and provenance/citations attached.

> You describe what data you *have* and what you *want*; Braidworks finds the path
> between them and runs it.

Most weavers are **keyless and need zero setup** — they call free public APIs
(UniProt, PDBe, Reactome, QuickGO, STRING, AlphaFold, NCBI). Install and run.

---

## For biologists: the bare minimum

Goal: start from a UniProt accession and get the protein's name and its experimental
PDB structures — crossing two databases (UniProt → PDBe) automatically.

### 1. Install

```bash
git clone https://github.com/rafaelmdc/braidworks
cd braidworks
uv sync --all-extras       # creates the environment and installs every weaver
```

(That uses [`uv`](https://docs.astral.sh/uv/). `uv run python yourscript.py` runs a
script inside the environment.)

### 2. Ask a question — from the shell

A value you have is a **Strand** (a typed fact, e.g. `protein.query = "P04637"`).
You tell Braidworks the strands you *have* and the strand *types* you *want*; it
finds the route across all installed weavers and runs it. From bash:

```bash
braidworks weave --have protein.query=P04637 --want protein.name,structure.pdb.ids
```

```
p53 (P04637)
  protein.name       Cellular tumor antigen p53
  structure.pdb.ids  9r2q; 9r2m; 8r1f; ... (25)
```

`"P04637"` is human p53; `"TP53"`, `"insulin"`, or any UniProt accession work too.

**Run a whole column of IDs** (one per line), and get a table back for your
spreadsheet/pandas:

```bash
braidworks weave --in-file accessions.txt --in-type protein.query \
    --want protein.name,protein.gene --format tsv > out.tsv

# or stream from a pipe straight into jq:
cat accessions.txt | braidworks weave --in-file - --in-type protein.query \
    --want structure.pdb.ids --format jsonl | jq .
```

**Drill every result** — fan one protein out into each of its structures, each then
described:

```bash
braidworks weave --have protein.query=P04637 \
    --want structure.pdb.title,structure.pdb.method --expand all --format tsv
```

Other commands: `braidworks weavers` (what's installed), `braidworks keys` (what
each weaver produces/consumes), `braidworks path --from … --to …` (preview a route),
`braidworks run <weaver> <capability>` (call one capability directly). Add `--help`
to any. Data goes to stdout; progress and a resolved/unresolved count go to stderr,
so pipes stay clean.

### 2b. …or from Python

```python
import asyncio
from braidworks.core import BraidRegistry, Braider, LocalExecutor, Strand, StrandSet
from uniprot_weaver import build_uniprot_weaver
from pdbe_weaver import build_pdbe_weaver

async def main():
    registry = BraidRegistry()
    registry.register(build_uniprot_weaver())   # gene/name/accession -> protein entry
    registry.register(build_pdbe_weaver())      # protein -> experimental structures

    braid = Braider(registry).plan(
        available_types=frozenset({"protein.query"}),
        target_types=frozenset({"protein.name", "structure.pdb.ids"}),
    )
    inputs = [StrandSet.from_strands("p53", [Strand("protein.query", "P04637")])]
    result = await LocalExecutor(registry).execute(braid, inputs)

    for entity in result.resolved:
        print(entity.get("protein.name").value)        # Cellular tumor antigen p53
        print(entity.get("structure.pdb.ids").value)   # ['9r2q', '9r2m', '8r1f', ...]

asyncio.run(main())
```

Pass a list of many `StrandSet`s to process a whole batch in one call.

### 3. Read the results

Every input lands in exactly one bucket of the result:

| Bucket | Meaning |
|---|---|
| `resolved` | The targets were produced — it worked. |
| `unresolved` | The route ran but found no match (a valid biological "nothing here"). |
| `review_queue` | The match was ambiguous; a human should pick. |
| `errors` | A structural problem (e.g. no route exists from your inputs). |

`len(resolved) + len(unresolved) + len(review_queue) + len(errors)` always equals the
number of inputs — nothing is silently dropped.

---

## What you can ask for (the weavers)

Two "hubs" — **organism** (NCBI taxid) and **protein** (UniProt accession) — are
bridged by `uniprot_weaver`, so a question can cross from one to the other.

| Weaver | From → To | Setup |
|---|---|---|
| `uniprot` | gene/name/accession → UniProt entry (+ name, gene, organism, **taxid**) | keyless API |
| `pdbe` | protein → experimental **PDB structures** (and one id → its detail) | keyless API |
| `alphafold` | protein → **predicted structure** model (pLDDT, model URL) | keyless API |
| `quickgo` | protein → **GO terms** by aspect (and one term → its detail) | keyless API |
| `reactome` | protein → **pathways** it participates in (and one id → its detail) | keyless API |
| `string` | protein → **interaction partners** (STRING network) | keyless API |
| `taxon` (`ncbi`) | organism name → **NCBI taxid** + lineage (and taxid → detail) | API, or local DB |
| `bacdive` | organism → **type-strain phenotypes** (gram stain, shape, oxygen…) | keyless API |
| `disbiome` | organism (taxid) → **microbe–disease** associations | bundled local DB |
| `example` | taxid → a couple of traits from a tiny CSV (reference weaver) | bundled |

The full, generated map of which weaver produces and consumes each key is in
[docs/keys-index.md](docs/keys-index.md), and an **offline interactive diagram** of
the whole network is at [docs/braidworks-network.html](docs/braidworks-network.html)
(open it in a browser; regenerate with `make view`).

### Capability naming — what a verb means

Every weaver capability is named by what it does, so you can predict its shape:

- **`resolve_*`** — fuzzy input → an identifier (e.g. a messy name → a UniProt accession).
- **`list_*`** — one identifier → a *set* of related identifiers (e.g. a protein → all its PDB ids).
- **`describe_*`** — one identifier → *that one entity's* attributes (e.g. one PDB id → its title/method/date).

---

## Fan-out: one input → many results

Some `list_*` capabilities emit a **set** identifier (e.g. `pdb.id`, `go.term`,
`pathway.reactome.id`). By default Braidworks keeps the single best one, but you can
ask it to **fan out** — fork one input into an independent child per result and keep
going. That turns "p53 → its structures" into "p53 → *each* structure, each then
drilled by `describe_structure`".

```python
from braidworks.core import ExpandPolicy

result = await LocalExecutor(registry).execute(
    braid, inputs,
    expand_policy=ExpandPolicy.all(),           # one child per pdb.id
    # or ExpandPolicy.top_k(5) to keep only the best five.
)
```

Children carry a `parent_id` back to the originating input, so you can regroup the
fanned leaves by the question that produced them. See
[docs/fanout-roadmap.md](docs/fanout-roadmap.md) for the model.

---

## Command-line tools

The **`braidworks`** command (installed with `braidworks-core`) is the query/inspect
front door — see [§2 above](#2-ask-a-question--from-the-shell):

```bash
braidworks weave --have TYPE=VALUE --want TYPE[,TYPE…]   # plan a route and run it
braidworks run <weaver> <capability> --have TYPE=VALUE   # call one capability directly
braidworks weavers                                       # list installed weavers + capabilities
braidworks keys [--produces TYPE | --consumes TYPE]      # what flows between weavers
braidworks path --from TYPE --to TYPE                    # preview a route, don't run it
braidworks references                                    # source citations
```

Inputs from flags, a file (`--in-file`, one value per line with `--in-type`, or a
CSV/TSV with type-id columns), or stdin (`--in-file -`). Output `--format
human|json|jsonl|tsv|csv`; `--expand all|top:K` to fan one→many.

`weaverkit` (a separate CLI) is the *build/inspect* toolkit:

```bash
uv run weaverkit view --out net.html # render the offline network diagram
make index                           # rebuild docs/keys-index.md + weavers-index.tsv
make view                            # rebuild docs/braidworks-network.html

taxon-weaver ensure                  # one-time: build the local NCBI taxonomy DB (optional)
```

`weaverkit` is also the toolkit for *building* a new weaver from a spec — see below.

---

## Repository layout

A [`uv`](https://docs.astral.sh/uv/) workspace monorepo:

```
braidworks/
├── braidworks-core/     # the framework: strands, capabilities, registry, braider, executor, cache
├── weaverkit/           # toolkit to add a weaver deterministically (spec → scaffold → verify) + CLIs
├── weavers/             # the data-source weavers (auto-discovered)
│   ├── uniprot_weaver/  #   the hinge: protein query → UniProt entry (+ taxid)
│   ├── pdbe_weaver/     #   protein → experimental structures
│   ├── ...              #   alphafold, quickgo, reactome, string, taxon, bacdive, disbiome, example
├── braidworks-arq/      # optional: distributed execution over arq/Redis
├── docs/                # architecture, usage, key index, network view, roadmaps
└── Makefile             # make help to list tasks
```

## Adding a weaver

New data sources are added through `weaverkit`'s **Spec → Scaffold → Implement →
Verify** loop, not hand-written. Start with [AGENTS.md](AGENTS.md) (the contributor
contract) and [weaverkit/README.md](weaverkit/README.md).

```bash
make new-weaver  SPEC=path/to/weaver.spec.toml DEST=weavers/<db>_weaver
make verify-weaver SPEC=path/to/weaver.spec.toml PACKAGE=<db>_weaver
```

## Development

```bash
make test     # run every package's test suite
make lint     # ruff across the workspace
make help     # list all tasks
```

Tests are per-package and the working directory matters — use `make test` (or see
[CONTRIBUTING.md](CONTRIBUTING.md)) rather than a bare `pytest` from the repo root.

## Documentation

| Doc | What it covers |
|---|---|
| [docs/index.md](docs/index.md) | Concepts and the result model |
| [docs/usage.md](docs/usage.md) | Install → register weavers → plan → run, with more examples |
| [docs/keys-index.md](docs/keys-index.md) | Catalog of keys that flow between weavers (generated) |
| [docs/architecture.md](docs/architecture.md) | Core abstractions, contracts, design decisions |
| [docs/fanout-roadmap.md](docs/fanout-roadmap.md) | Cardinality fan-out (one → many) model |
| [docs/database.md](docs/database.md) | Building / acquiring the NCBI taxonomy DB |
| [docs/repo-structure.md](docs/repo-structure.md) | Full repository layout |
| [AGENTS.md](AGENTS.md) | Contributor boundaries + the Spec→Scaffold→Implement→Verify loop |
| [weaverkit/README.md](weaverkit/README.md) | The spec/scaffold/conformance toolkit |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, testing, and how to add a new weaver |
</content>
</invoke>
