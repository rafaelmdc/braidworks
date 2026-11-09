# Browser execution interfaces

HTTP contracts for applications integrating with the optional local server.
For interactive use, see [the browser guide](../how-to/use-the-browser.md).

## Field search

GET `/api/find?q=WORDS&limit=N` (`limit` 1–100, default 10) returns
`{"ok": true, "matches": [...]}`, each match as in `FieldMatches.to_json()`: `type_id`,
`description`, `sources`, `inputs`, `consumers` and `score`. The ranking is
`bw.find`'s, so the browser, Python and `braidworks find` agree. An empty `q` or an
out-of-range `limit` returns `{"ok": false, "error": ...}`.

## Results and review

Run and resume responses carry `table` (`summary`, `want`, `columns`, `rows` as in
`Result.to_json()`, `sizes` giving each list's `shown`, `total` and `complete`,
`references`, and `review`: each paused row's `key`, `input`, `row`, `step`, `ambiguous`,
`candidates` and `warnings`) and `exports` (`csv`, `tsv`, `json`: exactly
`to_csv()`, `to_csv(sep="\t")`, `to_json()`). A run with paused rows and no run store
also returns `review_token`. POST `/api/review` with `token` and version-1 `decisions`
(the `/api/resume` format, `entity_key` = the item's `key`) continues the decided rows
through `Session` and returns the same envelope, with a new `review_token` while rows
remain paused. Tokens are single-use, held in memory (the most recent 32), and refused
with `{"ok": false}` once gone; an invalid decision is refused and keeps the review.

## Execution and persistence

Every run endpoint executes through the same `Session` as Python and the CLI, so a
query plans, caches, saves and resumes identically in all three. POST `/api/run` and
`/api/run/stream` accept a version-1 `persistence` object
from `QueryPersistence.to_json()`. Inspect with GET `/api/runs?run_db=...` and
`/api/run/status?run_db=...&run_id=...`. POST `/api/resume` or
`/api/resume/stream` takes `run_id`, `persistence` and optional version-1
`decisions`; query-policy overrides are rejected. Missing status files are not created.
Every `cache_db` and `run_db` path in these requests is resolved inside the server's
data directory (`braidworks serve --data-dir DIR`, default: the directory it was started
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
