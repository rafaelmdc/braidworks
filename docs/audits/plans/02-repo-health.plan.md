# Audit 02 fix plan

Spec: ../specs/02-repo-health.spec.md. Status: implementation completed except explicitly deferred findings. See ../README.md for final validation and delivery status. Never count a source-only report as a passing regression.

## A02-01 — Required lint currently reports hundreds of diagnostics

Status: fixed.

Pinned Ruff 0.16.10 in root/package Makefiles and scaffolded Makefiles. Reviewed safe import/export/UTC/annotation cleanup separately; destructured unused names preserved expressions, ClassVar marks shared fixture constants, intentional ValueError/optional metadata exception contracts have narrow documented noqa directives. Fixed Wikipedia's unclosed decompression wrapper with ExitStack; version 0.1.1 synchronized from spec-generated vocab. Added scaffold regression for builders with missing backends; generator now filters pinned capability backends to those actually wired. make lint passes; lint logs and mechanical patch are saved here. Conformance assertions remain intact.

Pin a reproducible lint tool/config; preserve baseline diagnostic log; review safe formatting separately from behavioral fixes; pass official lint without blanket ignores.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A02-02 — Some package metadata allows core versions older than required APIs

Status: fixed.

Historical symbol checks were followed by actual import, manifest JSON round-trip,
and every spec golden against archived core releases. Clean non-editable wheel
installs then confirmed all 17 weavers at their declared minima, with no checkout
imports: 0.1.8 (six bundled/local sources), 0.4.0 (Wikidata), 0.7.1 (BacDive,
NCBI, PDBe, STRING), 0.8.0 (GTDB), 0.11.2 (AGORA), and 0.12.0 (AlphaFold,
QuickGO, Reactome, UniProt after their new warning/concurrency APIs). Core 0.12.0
is built from this checkout; older versions are built from historical tags, not
claimed to be downloaded published releases. arq's clean 0.4.0 install passes
32 tests, 3 skipped; current full workspace tests also pass. Toolkit needs 0.12.0.

Scaffolds now pin the runtime verified with toolkit (>=0.12.0); its metadata
regression passes. Artifact CI rejects bare/low floors for known symbols and spec
fields; manually restoring UniProt's original 0.7.1 floor is rejected. Static guards
are lower-bound checks, not a substitute for new-API minimum-version tests.
Logs: core-floor-probes.json, minimum-core-installs-batch.log,
arq-clean-minimum-core.log; core-floors.md records exact scope.

Historical tag/source inventory saved in ../core-floors.md. Confirms UniProt/GTDB consumes_any requires 0.8.0, Wikidata parameters 0.4.0, unbounded Wikipedia is_not_found_status at least 0.1.7, and example Provenance at least 0.1.5. These are symbol/spec lower bounds, not certified minimum runtime versions; class-field evolution and fixtures still need testing. No speculative floors changed.

Inventory feature use against historical core APIs; raise floors to verified minima; bump affected weaver versions consistently via spec/scaffold; smoke-test minimum-version installs.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A02-03 — Software license for the packages is not declared

Status: fixed; user selected MIT for the software on 2026-10-04.

Root and all 20 package projects carry the existing NCBI MIT text, retaining its
Rafael/2026 copyright. Every package declares SPDX license = MIT and
license-files = [LICENSE]; package READMEs distinguish software from provider/data
licenses. Source provenance licenses were preserved. Independent package versions
were bumped coherently; non-NCBI vocab regenerated from specs, NCBI version edited
under its documented custom-plumbing exception. Toolkit core floor is >=0.12.0.

All 20 wheels/sdists rebuilt. Artifact checker asserts MIT License-Expression,
License-File, exact bundled license bytes and sdist license inclusion, then rehearses
clean installs/fixture/CLI/server. Local validation passes; publishing remains
unauthorized and no tags were created.

## A02-04 — Tags are automated, but there is no artifact build or publication workflow

Status: deferred by user.

Build/artifact verification and guarded manual publication workflow are prepared. Publishing/channel/account decisions are explicitly deferred by the user; no push, tag, workflow activation or publication has occurred.

## A02-05 — Workspace CI does not validate built package artifacts or clean installs

Status: fixed.

Built wheel/sdist artifacts for all 20 packages under /tmp. tools/check_artifacts.py checks every source/resource file, metadata versions and entry points, then installs actual wheels and the server extra in a fresh temporary environment outside the checkout. Bundled example lookup returns negative, imports reside in that venv, both CLI commands work, server app creates, 16 production plugins present. Example intentionally excludes discovery per its README. Added matching CI artifact job; local rehearsal passed. Hosted CI execution remains to be observed after a future authorized push.

Build wheels/sdists into temporary paths; install without workspace source overrides; assert resource files and entry points; add bounded artifact smoke CI after actual failure reproduction.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## Completion record

Record per finding: reproduction result, changed files, tests/commands, remaining risks, status (fixed / rejected with evidence / deferred with reason / awaiting decision). Do not mark this whole audit complete while requirements remain unresolved.
