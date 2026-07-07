# Contributing to gtdb_weaver

GTDB genome-based taxonomy (NCBI taxid / name -> GTDB species + lineage). Source: https://gtdb.ecogenomic.org (CC-BY-SA-4.0). Kind: `lookup`. Capabilities: `describe_gtdb_taxonomy`, `describe_gtdb_tree_placement`.

This weaver is **spec-driven**: `weaver.spec.toml` is the source of truth and
`vocab.py` is generated from it — never hand-edit `vocab.py`. The repo-wide loop
and boundaries are in [../../AGENTS.md](../../AGENTS.md); the spec field reference
is in [../../weaverkit/README.md](../../weaverkit/README.md); per-backend contracts
are in [../../weaverkit/docs/implementing-backends.md](../../weaverkit/docs/implementing-backends.md).

After any change, re-verify:

```bash
weaverkit verify --spec weaver.spec.toml --package gtdb_weaver --strict
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
  new `src/gtdb_weaver/backends/<name>.py` (`is_configured` / `fingerprint` / `fetch`).

## Keep the fixture & golden honest

- Golden inputs must resolve in whatever `--strict` runs against (a `build_gtdb_weaver_fixture()`
  or a configured backend). When the source data changes, bump the backend `fingerprint`
  and refresh the fixture/golden.

## Current outputs

This weaver currently produces: `gtdb.lineage`, `gtdb.taxon.id`, `gtdb.tree.rootpath`.

## Tree placement (`describe_gtdb_tree_placement`)

`local`-only. Emits `gtdb.tree.rootpath` — the organism's path from the root of the GTDB
reference tree to its species-representative leaf, as `[node_id, cumulative_depth]` steps.
Braidworks resolves per entity, so the *pairwise* patristic distance is computed by the
consumer from two paths via `gtdb_weaver.cophenetic` (deepest shared node). The geometry
(Newick parsing, root paths, cophenetic) lives in [`tree.py`](src/gtdb_weaver/tree.py); the
crosswalk join is species → representative `accession` → tree leaf.

Data: the reference trees are the GTDB `bac120.tree` + `ar53.tree` Newick files, acquired
by `setup.ensure_gtdb_trees` (consent-gated) alongside the crosswalk. The bundled fixture
(`data/fixture_tree.nwk`, 5 leaves) is what `verify --strict` runs against.

## Expansion notes

- **Confirm the tree URLs / leaf-label format on the live tree** — `setup.DEFAULT_*_TREE_URL`
  and the assumption that metadata `accession` equals the tree leaf label (GB_/RS_ prefix)
  are from the metadata schema, not yet observed against a downloaded tree. Capture a real
  `bac120.tree` excerpt and wire the live E2E before relying on real-data placement.
- Distance normalization (e.g. by tree diameter) is intentionally left to the consumer; the
  weaver emits raw geometry only.
- Node ids are a pre-order index of the fixed per-release tree — stable across calls, so the
  emitted paths cache per id. A release change re-numbers them (bump the fingerprint).
