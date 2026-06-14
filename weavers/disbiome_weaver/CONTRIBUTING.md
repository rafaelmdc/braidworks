# Contributing to disbiome_weaver

Disbiome microbe–disease associations (taxid -> diseases + direction). Source: https://disbiome.ugent.be (Open — cite Janssens et al., BMC Microbiology 2018 (doi:10.1186/s12866-018-1197-5); confirm reuse terms). Kind: `lookup`. Capabilities: `disbiome.list_diseases`.

This weaver is **spec-driven**: `weaver.spec.toml` is the source of truth and
`vocab.py` is generated from it — never hand-edit `vocab.py`. The repo-wide loop
and boundaries are in [../../AGENTS.md](../../AGENTS.md); the spec field reference
is in [../../weaverkit/README.md](../../weaverkit/README.md); per-backend contracts
are in [../../weaverkit/docs/implementing-backends.md](../../weaverkit/docs/implementing-backends.md).

After any change, re-verify:

```bash
weaverkit verify --spec weaver.spec.toml --package disbiome_weaver --strict
```

## Add an output to an existing capability

1. Add the `type_id` to the relevant `[[capability.group]].outputs` in `weaver.spec.toml`
   (or add a new group).
2. If it's a new *leaf* output, catalog it in `weaverkit.keys.OUTPUT_KEYS`; if it's a
   genuine *join key* others will consume, add it to `SHARED_KEYS` instead.
3. Regenerate vocab: `weaverkit new --spec weaver.spec.toml --dest . --force`
   (this only re-stamps generated files; your backend code is yours to edit).
4. Map it in each backend's `fetch` (`record.values[<type_id>] = ...`).
5. Add/adjust a `[[golden]]` example so the new output is verified.

## Add a capability or a backend

- **Capability:** add a `[[capability]]` block (consume a registered shared key),
  regenerate, and handle it in `fetch` (branch on `capability_id` if needed).
- **Backend:** add its name to `[weaver].backends`, regenerate, and implement the
  new `src/disbiome_weaver/backends/<name>.py` (`is_configured` / `fingerprint` / `fetch`).

## Keep the fixture & golden honest

- Golden runs against `build_disbiome_weaver_fixture()` (canned records in
  `src/disbiome_weaver/fixture.py` — Lactobacillus/1591 and Enterococcus/1350). The
  conformance and order-contract tests use the fixture too, so they run offline.
- After touching `setup.py` or the join, run the live E2E (`make test-live`,
  `BRAIDWORKS_RUN_LIVE=1`) to confirm the real API shapes still parse.

## Current outputs

`microbe.disease.names`, `microbe.disease.count` (summary group);
`microbe.disease.associations` (associations group); `microbe.disease.records`
(full group — the complete joined blob).

## How the local backend works

`setup.py` fetches the keyless Disbiome tables whole (`/experiment` + `/disease` +
`/organism` + `/publication`, ~7 MB), joins each experiment to its disease/organism/
publication, and writes one row per experiment into a SQLite indexed by NCBI taxid
(via `braidworks.core.localdb.ensure_local_db`). `/sample` and `/method` are just
`{id, name}` and already denormalized onto each experiment, so they aren't fetched.
Disbiome encodes missing values as the string `"None"` → normalized to `None` in
`_clean`. The fingerprint is a content hash of the fetched tables (no release tag).
`write_db` is shared by the live build and the fixture, so the schema lives in one
place.

## Expansion notes

- **Reverse lookup (disease → microbes).** Disbiome is equally queryable by disease;
  a second capability consuming a disease key (e.g. `disease.meddra.id` /
  `disease.name`, registered in `weaverkit.keys`) → the microbes Elevated/Reduced in
  it would make this an intermediate as well as a terminal weaver.
- **Emit the taxid back out.** Records carry `organism_ncbi_id`; the weaver could
  also *produce* `ncbi.taxon.id` so a disease-keyed entry links back to the organism
  layer.
- **Taxid granularity.** Lookups are exact-taxid; Disbiome organisms are often
  genus-level and its `organism_ncbi_id` may differ from a species taxid a caller
  holds (e.g. genus 1578 vs a species under it). A future lineage-aware roll-up
  (genus match for a species query) would raise recall — needs a defined policy.
- **Quantitative effect sizes.** `subject_value`/`control_value`/`ratio` are often
  absent; surfaced in the full blob when present, not interpreted.
