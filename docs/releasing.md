# Release rehearsal

Each package versions independently. This procedure prepares reviewable artifacts;
it does not publish packages or create tags. Package-index publication and credentials
are still maintainer decisions.

## Check the release contents

Read [NEXT](NEXT.md), [core migration](migrating-to-0.12.md) and the source READMEs.
Keep spec, project metadata and generated WEAVER_VERSION in agreement. Change the
spec and regenerate vocab; NCBI is the documented hand-written exception. Core
requirements are floors without ceilings. Review software MIT metadata separately
from source-data licenses.

For the complete development environment:

    make sync
    make lint
    make test
    make index

Tests are per-package and cwd-sensitive; use the Make targets. Live tests are opt-in
and are not part of ordinary CI. After API backend changes, run the relevant source's
small known-truth live test and record the date, coverage and upstream failures.
Avoid local dump/tree acquisition unless it is part of the intended release scope.

## Build and validate outside the checkout

Choose an empty output directory so stale artifacts cannot stand in for current ones:

    uv build --all-packages --out-dir /tmp/braidworks-release-artifacts
    python tools/check_artifacts.py /tmp/braidworks-release-artifacts --python 3.12

The checker validates all 20 wheel/sdist pairs: names, versions, licenses, source
modules, bundled resources, entry points, core dependency metadata and project URLs.
It installs the actual wheels into a temporary environment outside the checkout,
removes PYTHONPATH, checks module locations, executes the bundled example fixture,
checks source discovery and creates the browser app with the serve extra.

The artifact CI job repeats that rehearsal. A local pass does not prove a hosted CI
run or an external API's availability. Save command output and the tested Python/core
versions with the release review. The current minimum-core compatibility evidence
was obtained from clean installs of historical core-tag wheels and current weaver
wheels, with all spec golden examples; it is separate from latest-core workspace CI.

## Rehearse the user path

In the selected environment from [installation](installation.md):

    uv run --no-sync braidworks path --from protein.query --to structure.pdb.ids
    uv run --no-sync braidworks weave --have protein.query=P04637 --want protein.name,structure.pdb.ids --format json

For the browser, test typed and graph input, parameters, review pause, recipe/code
round trips, CSV/TSV/JSON downloads, keyboard navigation and retry after failure.
Include pasted lines, uploaded CSV/TSV, duplicate and heterogeneous rows, and cancellation. Default
ambiguity pause is intentional; do not use automatic selection merely to hide review
outcomes in a demo.

Distributed execution remains experimental. Inline tests check worker identity
mismatches and safe cache defaults; the rate script also has an isolated Lua emulator
check. These do not certify a real Redis fleet. HTTP hooks charge actual requests, including
pagination and redirects; rehearse shared Redis settings and supported backend wiring.
Rehearse matching worker/orchestrator deployments before production use.

Rehearse --archive with a new output path and inspect its initial inputs, effective
parameters, terminal outcomes and references. Archives preserve observations. Opt-in lookup caches and saved-run continuation
are separate implemented features; rehearse their [documented scope](persistence.md)
if they are included in your release. Further persistence scope remains under #143.

## Publication and tags

Keep publishing separate from these read-only/build checks. Before an initial
publication, settle the distribution channel, exact package set and version
availability, credentials or trusted publisher setup, and release notes. A publisher
should use the same validated artifacts and require an explicit release trigger.

Do not create tags manually. After an authorized merge/push to main, the CI workflow's
`tag` job creates package-version tags after tests, artifact checks and CodeQL succeed.
`make tags-check` is a read-only check for missing tags. Successful tagging does not
publish packages.


## Manual package workflow

[The package workflow](../.github/workflows/publish.yml) is a prepared PyPI option.
It runs only through GitHub Actions' manual workflow dispatch. The default
`publish=false` tests the checkout, builds and checks all distributions, and uploads
only the selected package's wheel and source archive as a downloadable workflow
artifact. This can be rehearsed from a branch without publishing or creating tags.

With `publish=true`, select the package's automatically created version tag as the
workflow ref. The staging check requires `refs/tags/<project-name>-v<version>` matching
that checkout's pyproject metadata. No push or tag event publishes automatically.
Only the publish job receives `id-token: write`; build jobs have read-only repository
permissions. The publish job downloads the checked artifact rather than rebuilding it.
The external actions are pinned to verified commit hashes.

Before enabling publication, the account owner needs to:

1. Confirm the distribution channel and ownership/availability of each PyPI project
   name. Configure only the packages intended for the initial release.
2. Create the repository's `pypi` GitHub environment with required reviewers and
   deployment restrictions appropriate to the account's release process.
3. Configure a PyPI trusted publisher (or a pending publisher for a new project):
   owner `rafaelmdc`, repository `braidworks`, workflow filename `publish.yml`,
   environment `pypi`. No long-lived upload token is needed.
4. Rehearse the default build-only dispatch. Review the uploaded distributions and
   release notes before a publishing dispatch from the exact package tag.

Publish core first. For a dependent package, the publishing preparation installs its
selected wheel against the package index without workspace overrides. An unpublished
core floor therefore blocks that package before upload. Next publish the toolkit and
chosen weavers; arq remains optional and experimental. Do not skip existing versions
or replace releases silently: an already published version requires a version bump.

Trusted publishing setup and permissions follow the official
[PyPI publishing instructions](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
and [pending publisher setup](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).
The workflow is prepared locally; remote Actions, account ownership and uploads have
not been exercised.
