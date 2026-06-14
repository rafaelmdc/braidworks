# disbiome_weaver

Microbe ↔ disease associations from **[Disbiome](https://disbiome.ugent.be)** (Ghent
University): given an organism by NCBI taxid, the diseases where its abundance is reported
**Elevated/Reduced** vs healthy controls (human host, MedDRA-coded). A terminal weaver off
the organism layer; chains straight behind `ncbi_weaver`.

- **Source:** https://disbiome.ugent.be (keyless JSON API on port 8080) · **License:** Open · **Cite:** https://doi.org/10.1186/s12866-018-1197-5 — Janssens et al., 2018
- **Backend:** `local` (a small SQLite built from the API; see below) · **Discoverable as** `disbiome`

## Capabilities

| Capability | Consumes | Produces (by group) |
|---|---|---|
| `disbiome.list_diseases` | `ncbi.taxon.id` | **summary:** `microbe.disease.names`, `microbe.disease.count` · **associations:** `microbe.disease.associations` · **full:** `microbe.disease.records` |

Output slices, light → heavy (the mapper emits only the requested group):

| Group | What you get |
|---|---|
| `summary` | distinct disease names + how many records |
| `associations` | one compact row per experiment: disease, direction, method, sample, host |
| `full` | the complete joined blob — every experiment/disease/organism/publication field, incl. the ~16 study-quality flags |

## The local backend (no dump file needed)

Disbiome publishes no dump file, but its API returns each table whole in one GET and the
whole dataset is ~7 MB. The `local` backend builds a small SQLite **once** — fetch
`/experiment` + `/disease` + `/organism` + `/publication`, join in-memory, index by NCBI
taxid — via the shared `braidworks.core.localdb` plumbing. The cache fingerprint is a
content hash of the fetched tables (Disbiome has no release tag).

## Use it

Build the DB once, then it chains straight off `ncbi_weaver`
(`organism.name → ncbi.taxon.id → microbe.disease.*`):

```python
from disbiome_weaver import build_disbiome_weaver_configured

# Builds the ~7 MB DB on first use (prompts on a TTY; set BRAIDWORKS_AUTO_DOWNLOAD=1
# or pass auto_setup=True non-interactively). Override location with db_path=.
weaver = build_disbiome_weaver_configured(auto_setup=True)
# In an app that wires a WeaverFactory, `disbiome_weaver.register(factory)` adds it as a provider.
```

From the `braidworks` CLI (auto-discovered once installed; the DB is built on first use):

```bash
braidworks run disbiome disbiome.list_diseases --have ncbi.taxon.id=816
```

## Develop

```bash
make verify     # spec ↔ manifest, reachability, fingerprints (--strict adds golden vs the fixture)
make test       # conformance + contract + behavior, offline (live E2E self-skips)
make test-live  # opt-in: build the real DB from the API and resolve a known taxid
```

Extend it ([CONTRIBUTING.md](CONTRIBUTING.md)): reverse disease→microbe lookup, emitting
the taxid back out, etc. Build loop & boundaries: [AGENTS.md](../../AGENTS.md).
