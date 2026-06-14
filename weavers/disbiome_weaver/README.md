# disbiome_weaver

Microbe ↔ disease associations from **[Disbiome](https://disbiome.ugent.be)** (Ghent
University): given an organism by NCBI taxid, the diseases where its abundance is
reported **Elevated/Reduced** vs healthy controls (human host, MedDRA-coded).

- **Source:** https://disbiome.ugent.be (keyless JSON API on port 8080)
- **License:** Open — cite Janssens et al., BMC Microbiology 2018
  (doi:10.1186/s12866-018-1197-5); confirm reuse terms.
- **Consumes:** `ncbi.taxon.id` · **Kind:** `lookup` · **Backend:** `local`

## Output slices (light → heavy)

One capability, `disbiome.list_diseases`, with three output groups so a caller
asks for exactly what a prompt needs (the mapper emits only the requested slice):

| Group | Output | What you get |
|---|---|---|
| `summary` | `microbe.disease.names`, `microbe.disease.count` | distinct disease names + how many records |
| `associations` | `microbe.disease.associations` | one compact row per experiment: disease, direction, method, sample, host |
| `full` | `microbe.disease.records` | the **complete joined blob** — every experiment/disease/organism/publication field, incl. the ~16 study-quality flags |

## The local backend (no dump file needed)

Disbiome publishes no dump file, but its API returns each table whole in one GET and
the whole dataset is ~7 MB. The `local` backend builds a small SQLite once — fetch
`/experiment` + `/disease` + `/organism` + `/publication`, join in-memory, index by
NCBI taxid — via the shared `braidworks.core.localdb` plumbing. The cache fingerprint
is a content hash of the fetched tables (Disbiome has no release tag).

```python
from disbiome_weaver import build_disbiome_weaver_configured

# Builds the ~7 MB DB on first use (prompts on a TTY; set BRAIDWORKS_AUTO_DOWNLOAD=1
# or pass auto_setup=True non-interactively). Override location with db_path=.
weaver = build_disbiome_weaver_configured(auto_setup=True)
```

```bash
make verify     # weaver matches weaver.spec.toml
make test       # conformance + contract + behavior (live E2E self-skips)
make test-live  # opt-in: build the real DB from the API and resolve a known taxid
```

## Registering this weaver

```python
from braidworks.core import WeaverFactory
import disbiome_weaver

factory = WeaverFactory()
disbiome_weaver.register(factory)        # makes "disbiome" buildable
```

It's taxid-keyed, so it chains straight off `taxon_weaver`:
`organism.name → [taxon_weaver] → ncbi.taxon.id → [disbiome_weaver] → microbe.disease.*`.
See [CONTRIBUTING.md](CONTRIBUTING.md) for extending it (reverse disease→microbe
lookup, emitting the NCBI taxid back out, etc.).
