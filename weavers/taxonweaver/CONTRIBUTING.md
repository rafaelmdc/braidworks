# Contributing to taxonweaver

NCBI Taxonomy resolver (name/taxid → taxonomy + lineage). Source:
https://www.ncbi.nlm.nih.gov/taxonomy (Public Domain). Kind: `resolver`.
Capabilities: `ncbi.resolve_name`, `ncbi.resolve_taxid`. weaver_id: `ncbi`.

> **This is the "bring your own plumbing" reference weaver** (see
> [../../weaverkit/docs/decisions.md](../../weaverkit/docs/decisions.md)). Unlike a
> scaffolded weaver, it does **not** use the shared `braidworks.core` runtime: it has
> its own `dispatch.py`, a typed `TaxonMatch` intermediate, and a resolver-specific
> `mapper.py`, and its `vocab.py` is **hand-written** (not generated). So the generic
> "regenerate vocab with `weaverkit new --force`" recipe does **not** apply here —
> edit `vocab.py` / `mapper.py` / the backends directly, keeping the manifest in sync
> with `weaver.spec.toml` (`weaverkit verify` checks that).

After any change, re-verify (runs golden against the mini fixture — no 1.2 GB build):

```bash
weaverkit verify --spec weaver.spec.toml --package taxonweaver --strict
make test
```

## Conform-via-manifest contract

`weaverkit verify` only requires that `MANIFEST` matches `weaver.spec.toml`,
fingerprints are real, and golden passes — not that you use the shared runtime. So
when you extend taxonweaver, keep `weaver.spec.toml` and `vocab.py` in lockstep and
the rest is your call.

## Add an output / capability

1. Add the `type_id` to the right `[[capability.group]].outputs` in `weaver.spec.toml`
   **and** mirror it in `vocab.py` (hand-written here). New leaf outputs → catalog in
   `weaverkit.keys.OUTPUT_KEYS`; new join keys → `SHARED_KEYS`.
2. Produce it in the backends (`backends/local.py`, `backends/datasets_v2.py`) by
   filling the typed `TaxonMatch`, and emit it in `mapper.py`.
3. Add a `[[golden]]` whose input resolves in the mini fixture
   (`src/taxonweaver/fixture.py`, the *Faecalibacterium* clade).

## Backends

- `local` — SQLite built from the NCBI taxdump via `setup.py` (delegates the generic
  download/build/lock/publish to `braidworks.core.localdb`; only `db_is_valid` /
  `_build` are taxonomy-specific).
- `api` — NCBI Datasets v2 (`datasets_v2.py`), injectable `httpx.AsyncClient`.
- Two builders: `build_taxonweaver()` (zero-config introspection, verify's target)
  and `build_ncbi_weaver(...)` (configured, with consent-gated DB acquisition).

## Expansion notes

- The `datasets_v2` API JSON shapes were validated against a fake; the live E2E
  (`tests/test_e2e_live.py`, `BRAIDWORKS_RUN_LIVE=1`) is the way to confirm against
  real NCBI — run it after API-touching changes.
- Could later adopt the shared core runtime if the custom `TaxonMatch` richness stops
  earning its keep; for now it stays custom on purpose, as the divergent reference.
