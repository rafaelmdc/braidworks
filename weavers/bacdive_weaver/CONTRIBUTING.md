# Contributing to bacdive_weaver

BacDive type-strain phenotypes (scientific name -> microbe traits). Source: https://bacdive.dsmz.de (CC BY 4.0 (BacDive / DSMZ; cite https://doi.org/10.1093/nar/gkab961)). Kind: `lookup`. Capabilities: `describe_traits`.

This weaver is **spec-driven**: `weaver.spec.toml` is the source of truth and
`vocab.py` is generated from it — never hand-edit `vocab.py`. The repo-wide loop
and boundaries are in [../../AGENTS.md](../../AGENTS.md); the spec field reference
is in [../../weaverkit/README.md](../../weaverkit/README.md); per-backend contracts
are in [../../weaverkit/docs/implementing-backends.md](../../weaverkit/docs/implementing-backends.md).

After any change, re-verify:

```bash
weaverkit verify --spec weaver.spec.toml --package bacdive_weaver --strict
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
  new `src/bacdive_weaver/backends/<name>.py` (`is_configured` / `fingerprint` / `fetch`).

## Keep the fixture & golden honest

- Golden inputs must resolve in whatever `--strict` runs against (a `build_bacdive_weaver_fixture()`
  or a configured backend). When the source data changes, bump the backend `fingerprint`
  and refresh the fixture/golden.

## Current outputs

This weaver currently produces: `microbe.trait.cell_shape`, `microbe.trait.gram_stain`, `microbe.trait.motility`, `microbe.trait.optimum_ph`, `microbe.trait.optimum_temp`, `microbe.trait.oxygen_tolerance`, `microbe.trait.spore_formation`.

## Expansion notes

**MVP scope: the type strain as the species representative.** BacDive is
*strain-level* and offers no species-aggregation endpoint, so this weaver resolves
a species' **type strain** (the record flagged `"type strain": "yes"`) and maps its
traits. The type strain is the nomenclatural standard and BacDive curates one for
~98% of validly described species, so it's a sound, deterministic representative —
but it is *one strain*, not the species as a whole. The point of braidworks is to
ease and interlink, so this is meant to grow:

- **Aggregate-across-strains mode.** A capability that fetches *all* strains of the
  species and aggregates a trait (majority vote / value distribution / "varies"),
  so e.g. oxygen tolerance reflects the species rather than one isolate. Needs a
  policy for conflicts and for emitting confidence/spread.
- **Strain-level lookups.** A capability keyed on a strain identifier (BacDive id,
  or `culturecollectionno` like "DSM 30083") → that exact strain's full profile.
  BacDive already has `fetch/{id}` and `culturecollectionno/{n}` endpoints for this.
- **More outputs.** Records carry far more than the seven traits mapped here —
  metabolite utilization, enzymes (→ `enzyme.ec`), 16S/genome accessions, isolation
  source/ecology, antibiotic resistance. Several would make this an *intermediate*
  weaver (e.g. emit `enzyme.ec` / `chem.chebi.id` cross-refs as their own group).
- **Carry the NCBI taxid out.** Records contain `General → NCBI tax id`; emitting it
  would let bacdive link *back* to `ncbi.taxon.id` (currently we only consume names).

### Known limitations / data quirks

- **Scan cost.** No "type strains only" filter exists, so finding the type strain
  pages the taxon ID list and `fetch`es records until the flag matches, bounded by
  `max_strains_scanned` (default 200; *E. coli* alone has ~1,884 strains). Mitigate
  with **batch fetch** (the endpoint takes ≤100 ids/call — confirm the multi-id
  separator against the live API) and a cache. If no type strain is found within
  the cap → NO_MATCH.
- **Subfield shape.** BacDive returns a subfield as a *dict* for one entry and a
  *list* for many; the backend normalizes via `_first` / `_as_list`. Preserve that
  when adding fields.
- **Sparse traits.** `spore_formation` / `optimum_ph` are often absent per record;
  they're emitted only when present (a missing trait is not an error).
- **Name parsing.** Only `genus species` is used for the taxon path; subspecies and
  multi-word qualifiers are dropped — revisit if you add subspecies resolution.
- After any parsing change, run the live E2E: `BRAIDWORKS_RUN_LIVE=1 make test-live`
  (`tests/test_e2e_live.py`) to confirm the paths still match the real schema.
