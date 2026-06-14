# Contributing to string_weaver

STRING protein-protein interactions (accession -> partners + scores). Source: https://string-db.org (CC BY 4.0 (STRING; Szklarczyk et al., cite https://doi.org/10.1093/nar/gkac1000)). Kind: `lookup`. Capabilities: `list_interactions`.

This weaver is **spec-driven**: `weaver.spec.toml` is the source of truth and
`vocab.py` is generated from it — never hand-edit `vocab.py`. The repo-wide loop
and boundaries are in [../../AGENTS.md](../../AGENTS.md); the spec field reference
is in [../../weaverkit/README.md](../../weaverkit/README.md); per-backend contracts
are in [../../weaverkit/docs/implementing-backends.md](../../weaverkit/docs/implementing-backends.md).

After any change, re-verify:

```bash
weaverkit verify --spec weaver.spec.toml --package string_weaver --strict
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
  new `src/string_weaver/backends/<name>.py` (`is_configured` / `fingerprint` / `fetch`).

## Keep the fixture & golden honest

- Golden inputs must resolve in whatever `--strict` runs against (a `build_string_weaver_fixture()`
  or a configured backend). When the source data changes, bump the backend `fingerprint`
  and refresh the fixture/golden.

## Current outputs

See [README.md](README.md) and the `weaver.spec.toml` for this weaver's current capabilities and outputs — the spec is the source of truth (a frozen copy here only drifts).

## Expansion notes

<!-- Weaver-specific notes: what's intentionally left out, what's easy to add next,
     data quirks, columns not yet mapped, etc. Fill this in as you build. -->
- Record source-specific quirks, columns not yet mapped, and next-capability ideas here as they surface.
