# Repository health and maintainability audit

## Executive assessment

The repository has a coherent contributor path for adding weavers: a uv workspace, automatic `weavers/*` discovery in Make targets, a spec-driven scaffold, generated implementation/contribution notes, per-package tests, and a strict verifier. The inventory contains 20 package projects (core, weaverkit, arq, and 17 weavers); all 17 weavers have specs and per-weaver CONTRIBUTING.md files. A static comparison found no disagreement among the 17 weaver spec versions, project versions, and `WEAVER_VERSION` constants.

The current release baseline is not ready to call green. The available Ruff 0.16.10 reports 381 diagnostics across the same source/test directories listed by `make lint`; the exact Make target could not run because this environment has no `make`. `make test` was also unavailable (`make` absent; system Python has no pytest). Installing dependencies was out of scope, so test, wheel, and sdist behavior remain unverified. Separately, some released-package metadata permits core versions below APIs their specs use, and the repository has no explicit software license or package publication workflow. Those gaps matter when consumers install projects individually rather than through the workspace.

## Strengths worth preserving

- Root uv workspace membership includes all weavers by glob; root Make targets discover weavers automatically ([pyproject.toml](../../../pyproject.toml), [Makefile](../../../Makefile)).
- Contributor docs describe setup, cwd-sensitive package test execution, the scaffold loop, independent package versions, and core compatibility floors ([CONTRIBUTING.md](../../../CONTRIBUTING.md)).
- CI runs lint and all package suites on pushes to main and pull requests ([ci.yml](../../../.github/workflows/ci.yml)). A separate scheduled/on-demand live workflow keeps external API calls out of required CI ([live.yml](../../../.github/workflows/live.yml)).
- `weaverkit` makes the spec → scaffold → implement → strict verify lifecycle explicit, and generated packages include both one-time implementation steps and ongoing contribution guidance ([scaffold.py](../../../weaverkit/src/weaverkit/scaffold.py), [scaffold.py](../../../weaverkit/src/weaverkit/scaffold.py)).
- CI syncs the locked workspace before testing. Dependency bot updates GitHub Actions weekly; this is useful maintenance, though Python dependencies are not included in its update configuration ([ci.yml](../../../.github/workflows/ci.yml), [dependabot.yml](../../../.github/dependabot.yml)).
- Release-tag automation has narrow `contents: write` permissions and derives independent package tags from project versions ([release-tags.yml](../../../.github/workflows/ci.yml)). It is tag automation, not package publishing.

## Findings

### 1. Required lint currently reports hundreds of diagnostics

- **Category:** release blocker
- **Severity:** high
- **Confidence:** confirmed for Ruff 0.16.10; exact `make lint` CI invocation needs verification because `make` is unavailable here
- **Evidence:** [Makefile](../../../Makefile) defines lint paths and invokes unpinned `uvx ruff check` at line 74. Running installed `ruff 0.16.10 check` over those same source/test directories returned exit code 1 with **381 errors**, 241 fixable and 92 additional unsafe fixes. The output included import-order errors and unused noqa diagnostics as well as other rule violations.
- **Impact:** CI always runs lint before tests, so a matching Ruff version makes the CI job fail and prevents a green pull-request check. Contributors also cannot tell which Ruff version defines the repository contract because `uvx ruff` is not pinned in project metadata or the lockfile.
- **Reproduction/reasoning:** `ruff check braidworks-core/src braidworks-core/tests weaverkit/src weaverkit/tests braidworks-arq/src braidworks-arq/tests` plus each `weavers/*/src` and `weavers/*/tests` directory; 381 diagnostics. `make lint` itself stopped immediately with `command not found: make`.
- **Smallest useful remedy:** pin Ruff in a development dependency group/lockfile (or pin the `uvx --from ruff==...` invocation), then resolve the diagnostics under that documented version.
- **Effort:** M
- **Validation:** from the documented clean setup, `make lint` exits 0 using the same pinned Ruff version on CI and locally.

### 2. Some package metadata allows core versions older than required APIs

- **Category:** first-release improvement
- **Severity:** high
- **Confidence:** confirmed
- **Evidence:** repo guidance says `consumes_any` needs `braidworks-core>=0.8.0` ([AGENTS.md](../../../AGENTS.md)). `uniprot_weaver` declares `braidworks-core>=0.7.1` ([pyproject.toml](../../../weavers/uniprot_weaver/pyproject.toml)) while its spec uses `consumes_any` ([weaver.spec.toml](../../../weavers/uniprot_weaver/weaver.spec.toml)). `gtdb_weaver` also uses `consumes_any` ([weaver.spec.toml](../../../weavers/gtdb_weaver/weaver.spec.toml)) but declares bare `braidworks-core` ([pyproject.toml](../../../weavers/gtdb_weaver/pyproject.toml)). At least five other weavers declare bare core dependencies; workspace source overrides can mask these minimum-version declarations during workspace development.
- **Impact:** an independent package installation can satisfy metadata with an older core that lacks `consumes_any` or other newer capability fields, then fail during import, manifest construction, or planning. Workspace CI resolves the in-repo core, so it does not prove those package floors.
- **Reproduction/reasoning:** compare each spec's required capability features to its package's declared dependency floor. The examples above directly contradict the repository's documented minimum.
- **Smallest useful remedy:** raise each package's `braidworks-core>=` floor to the first release containing every API used by its spec/runtime; add a small metadata check so future specs cannot outgrow their declared floor.
- **Effort:** S
- **Validation:** for each affected package, create a clean environment using only published dependencies and verify import, manifest construction, and strict golden verification against the declared minimum core version.

### 3. Software license for the packages is not declared

- **Category:** release blocker
- **Severity:** high
- **Confidence:** confirmed that repository/package declarations are absent; legal consequences need maintainer review
- **Evidence:** no root `LICENSE`/`COPYING` file is tracked, and none of the 20 project pyprojects declares `project.license` or `license-files`. The only tracked license file is [weavers/ncbi_weaver/LICENSE](../../../weavers/ncbi_weaver/LICENSE), which pertains to that package/source. Weaver source-data licenses appear in specs (for example [weaver.spec.toml](../../../weavers/uniprot_weaver/weaver.spec.toml)); those are upstream data provenance and do not state the license for Braidworks software.
- **Impact:** users and downstream packagers cannot identify permissions or obligations for the framework and most package code from the repository or package metadata. A data-source license can also be mistaken for a software license.
- **Reproduction/reasoning:** tracked license inventory plus parsed project metadata; NCBI's file is the sole repository license path found.
- **Smallest useful remedy:** select and review a software license for the code, add the root license text, and declare/carry it in every independently distributed package (or document why package licenses differ).
- **Effort:** S, excluding legal review
- **Validation:** inspect built wheel and sdist metadata/files for each package and confirm the declared code license is distinct from each weaver's upstream data license.

### 4. Tags are automated, but there is no artifact build or publication workflow

- **Category:** first-release improvement
- **Severity:** medium
- **Confidence:** confirmed from the checked-in workflow inventory
- **Evidence:** the only release workflow is [release-tags.yml](../../../.github/workflows/ci.yml), which configures git and runs `tools/release_tags.py create`; it does not build or upload distributions. The checked-in `.github/workflows` inventory contains CI, CodeQL, live tests, and tag creation, with no release/publish workflow. Package versions are independent as described in [CONTRIBUTING.md](../../../CONTRIBUTING.md).
- **Impact:** after a version bump, a tag is created but no wheel/sdist is produced or published by repository automation. A first release therefore needs a separate documented/manual publishing procedure, including per-package dependency/source handling and credentials.
- **Reproduction/reasoning:** inspect all tracked workflow files and the release tag script; no build, PyPI upload, or trusted-publishing step exists.
- **Smallest useful remedy:** document the manual release/build/publish procedure before the first public release, or add a narrowly scoped tag-triggered publishing workflow after validating clean artifacts. Keep credentials in GitHub OIDC/trusted publishing or scoped secrets, not repository files.
- **Effort:** M
- **Validation:** rehearse one package release from a clean checkout; verify tag, wheel/sdist contents, metadata, and installation in a fresh environment. Confirm the workflow only publishes the intended package/version.

### 5. Workspace CI does not validate built package artifacts or clean installs

- **Category:** first-release improvement
- **Severity:** medium
- **Confidence:** confirmed about CI coverage; packaging failures need verification
- **Evidence:** [ci.yml](../../../.github/workflows/ci.yml) performs `uv sync --all-extras`, then lint and tests. No workflow builds wheels/sdists or installs them in isolated environments. Package pyprojects select Hatchling and explicit source package directories, e.g. [weaverkit/pyproject.toml](../../../weaverkit/pyproject.toml) and [weaverkit/pyproject.toml](../../../weaverkit/pyproject.toml). Several packages include runtime data files, including [agora2_crosswalk.tsv](../../../weavers/agora_weaver/src/agora_weaver/data/agora2_crosswalk.tsv) and [example_traits.csv](../../../weavers/example_weaver/src/example_weaver/data/example_traits.csv); their presence in source does not establish wheel/sdist inclusion.
- **Impact:** workspace imports and tests use source trees and workspace dependency overrides. They can pass while a standalone artifact omits runtime assets, has incomplete metadata, or cannot resolve the declared dependency floor.
- **Reproduction/reasoning:** CI contains no build/install step. In this audit, an artifact build was not attempted because the environment lacks `make`/pytest and bootstrapping build dependencies would exceed the audit's no-install constraint.
- **Smallest useful remedy:** add a bounded CI smoke job that builds each package (or at minimum core, toolkit, and all weavers), inspects expected data files/entry points in artifacts, then installs representative artifacts into a clean environment without workspace sources.
- **Effort:** M
- **Validation:** isolated installs import each package, discover entry points, and load any packaged resource used by a fixture/configured builder; artifact contents are checked for expected data files.

## Verification log

- Read `.audit-local/COMMON.md`, `.audit-local/prompts/02-repo-health.md`, and root `AGENTS.md`; inspected root and package pyprojects, uv lock metadata, Makefiles, CI/live/release-tag/CodeQL workflows, Dependabot configuration, contributor guidance, release-tag tooling references, package assets, and license paths.
- `git status --short`: only the supplied `.audit-local/` audit files were untracked before this report; no production files were changed.
- Workspace inventory: 20 projects total: core, weaverkit, arq, and 17 weavers. All 17 weavers have `weaver.spec.toml` and `CONTRIBUTING.md`; versions matched among spec, pyproject, and parsed `WEAVER_VERSION` constants in this static check.
- `make lint`: not run; shell returned `command not found: make` (exit 127).
- Equivalent direct Ruff check over the Makefile path set, using installed `ruff 0.16.10`: failed, 381 errors reported (241 fixable; 92 additional unsafe fixes). Exact output included import sorting, `__all__` sorting, unused noqa, and additional rule failures. `uvx ruff` is not pinned in project metadata or `uv.lock`, so CI's resolved tool version can differ.
- `make test`: not run; `make` is unavailable. No root `.venv` was present and system `python -m pytest --version` reported `No module named pytest`. No dependency installation was attempted. Consequently no test totals, skips, or failures can be claimed.
- No live tests, package builds, clean wheel/sdist installs, or publication were attempted. No credentials were assumed.

## Top five actions

1. Pin the Ruff version and return the required lint job to green.
2. Raise each weaver's declared core floor to match the core APIs used by its spec, especially `consumes_any`.
3. Choose and declare a software license for every independently distributed package; keep upstream data licenses separately attributed.
4. Validate wheels/sdists and standalone installs, including resource files and entry points.
5. Document or automate artifact release/publication; tags alone do not deliver packages to users.

## Open questions and limitations

- What software license should cover the core, toolkit, arq integration, and weaver implementation code? Is a package-specific exception intended for NCBI?
- Is PyPI/public publishing planned, or are package tags currently intended only for source release tracking?
- Are the Ruff 0.16.10 diagnostics current CI's exact set? `make lint` could not be run, and the Makefile resolves `uvx ruff` without a version pin.
- Which minimum `braidworks-core` release introduced all APIs each existing weaver uses? This audit confirmed documented `consumes_any` mismatches, but did not execute every package against historical core releases.
- Whether source assets are included in distributions remains unverified because no wheel or sdist was built in this constrained environment.

Release tagging subsequently moved into the CI `tag` job under #86; historical
references above now link to that maintained workflow.
