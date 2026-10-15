# Workflow consolidation — #86

## Decision and implementation

Combine deterministic validation and security analysis in `ci.yml`, retaining the
existing `test`, `artifacts` and `analyze` job identities. Move the automatic `tag`
job into the same workflow and require all three checks to succeed before main
pushes can create tags. Keep manual publication and network-dependent live E2E
separate; their triggers and failure meaning differ from merge validation.

The workflow defaults to read-only contents permission. Only analysis receives
security-event upload permission, and only the main-push tagging job receives
contents write permission. PR source code is never tagged. Weekly scheduled runs
execute analysis alone; tests/artifact checks/tagging skip. Concurrency separates
scheduled and push/PR runs so a security scan does not cancel validation.

GitHub's [workflow syntax reference](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
documents job dependencies, skipped/failed prerequisite behavior and per-job token
permissions. Its [code-scanning configuration reference](https://docs.github.com/en/code-security/reference/code-scanning/workflow-configuration-options)
explains why scheduled scans remain useful for unchanged code. Those documented
semantics support the event/dependency choices here.

| Event | Tests/artifacts | CodeQL | Automatic tags |
|---|---|---|---|
| PR to main | Run | Run | Never |
| PR to another base | Run | Skip, preserving previous scope | Never |
| Push to main | Run | Run | Only after every prerequisite succeeds |
| Weekly schedule | Skip | Run | Never |

## Verification

Actionlint 1.7.12, already isolated under `.audit-local/tools`, validates all workflows.
The release-tool unit suite passes. Existing release actions/versions and the tagging
script are unchanged. Branch protection inspection reported main unprotected; existing
job names are retained regardless. No workflow was dispatched, no tag was created and
publication remains deferred. GitHub-hosted execution will be verified after an authorized
PR/merge; local validation cannot simulate hosted CodeQL permissions or runners.
