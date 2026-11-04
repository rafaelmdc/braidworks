# Browser execution interfaces

HTTP contracts for applications integrating with the optional local server.
For interactive use, see [the browser guide](../how-to/use-the-browser.md).

## Execution and persistence

POST `/api/run` and `/api/run/stream` accept a version-1 `persistence` object
from `QueryPersistence.to_json()`. Inspect with GET `/api/runs?run_db=...` and
`/api/run/status?run_db=...&run_id=...`. POST `/api/resume` or
`/api/resume/stream` takes `run_id`, `persistence` and optional version-1
`decisions`; query-policy overrides are rejected. Missing status files are not created.
Every `cache_db` and `run_db` path in these requests is resolved inside the server's
data directory (`weaverkit serve --data-dir DIR`, default: the directory it was started
in). Relative paths resolve against it; a path that resolves outside it, including
through `..` or a symlink, returns `{"ok": false}` with an explanation and no file is
opened or created. `/api/code` only renders commands and does not open files.
Binding with a `--host` other than localhost prints a warning describing this exposure.

See [storage operations](persistence.md) for leases, retention and schema limits.


## Generated artifacts and discovery

Generated single and batch Python examples use the public core query service
(`braidworks-core>=0.20.0`). They print `ExecutionResult.to_json()` and need neither
weaverkit nor FastAPI at execution time; batch inputs retain order and source rows.
The browser keeps its own table/summary response envelope. Generated CLI commands
quote literal input values and preserve effective parameters and query policies.



For strict/tolerant plugin loading and worker ownership, see
[discovery reference](discovery.md).
