# Contributing to disbiome_weaver

Disbiome microbe–disease associations (taxid -> diseases + direction). Source: https://disbiome.ugent.be (Open). Kind: `lookup`. Capabilities: `disbiome.list_diseases`.

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
3. Follow the scratch-generation workflow below; selectively copy the generated vocab.
4. Map it in each backend's `fetch` (`record.values[<type_id>] = ...`).
5. Add/adjust a `[[golden]]` example so the new output is verified.

## Add a capability or a backend

- **Capability:** add a `[[capability]]` block (consume a registered shared key),
  generate in scratch, review the diff, and handle it in `fetch` (branch on `capability_id` if needed).
- **Backend:** add its name to `[weaver].backends`, generate in scratch, and selectively add the
  new `src/disbiome_weaver/backends/<name>.py` (`is_configured` / `fingerprint` / `fetch`).

## Safe regeneration of an implemented package

Run from this package directory after editing the spec:

```bash
scratch_dir=$(mktemp -d)
weaverkit new --spec weaver.spec.toml --dest "$scratch_dir/package"
diff -ru --exclude=.git --exclude=__pycache__ --exclude=.pytest_cache . "$scratch_dir/package"
# diff exits 1 when differences exist; review them before the next command.
cp "$scratch_dir/package/src/disbiome_weaver/vocab.py" src/disbiome_weaver/vocab.py
```

Copy only the reviewed generated vocab. Merge capability/backend additions
selectively into the existing implementation, factories, tests and metadata;
do not copy placeholder backends over working code. Preserve your configuration
builders, source-specific policies and contributor notes. Inspect `git diff`,
run package tests and strict verification, then remove the scratch directory.

`weaverkit new --force` overwrites generated paths, including implemented
backends, factories and tests. It does not merge or preserve your edits.
Never run it against an implemented package. The handwritten NCBI reference
is exempt: edit its custom vocab manually instead of copying scaffold vocab.

## Keep the fixture & golden honest

- Golden inputs must resolve in whatever `--strict` runs against (a `build_disbiome_weaver_fixture()`
  or a configured backend). When the source data changes, bump the backend `fingerprint`
  and refresh the fixture/golden.

## Current outputs

See [README.md](README.md) and `weaver.spec.toml` for the current output keys and groups.

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
