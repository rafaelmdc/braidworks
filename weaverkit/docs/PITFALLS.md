# Pitfalls — the short list

The handful of mistakes that actually recur when building a weaver. Each is a
do/don't pair. Keep this list short; if it grows, the important ones get lost.

1. **fetch must return one record per input, in order.**
   Don't drop misses, reorder, de-duplicate, or merge. Do append exactly one
   `Record` per query in the same order — a miss is `found=False` (or
   `MatchStatus.NO_MATCH`), still in its slot. The dispatch aligns by position.

2. **A miss is data, not an error.**
   Don't raise when a lookup finds nothing. Do return `found=False` /
   `NO_MATCH`. Reserve exceptions for *structural* faults (misconfiguration),
   surfaced via `is_configured` / construction — not per-entity data outcomes.

3. **Never return `""` or `"unknown"` from `fingerprint()`.**
   That silently disables cache invalidation (conformance rejects it). Do return
   a stable, version-specific string that changes iff the data changes (release
   tag, dump date, content checksum).

4. **Don't hand-edit `vocab.py`.**
   It's generated from `weaver.spec.toml`. Edit the spec and re-run
   `weaverkit new --force`; `verify` checks the two stay in sync.

5. **`consumes` must be a registered shared key.**
   Don't invent a private input type — that makes an unreachable island weaver.
   Do pick from `weaverkit/src/weaverkit/keys.py`, or add a genuinely new bridge
   key there in the same PR.

6. **`source_sample` must be real.**
   Don't invent a plausible-looking schema. Do paste an actual snippet of the
   source — it's the anti-hallucination guard proving the schema was observed.

7. **Emit only this capability's produced type_ids.**
   `record.values` keys should be the produced `type_id`s from the spec (the
   mapper filters to the requested subset). Don't stuff raw source column names
   in — map them to the spec's output type_ids.

8. **Don't weaken the contract/conformance tests to go green.**
   If `WeaverConformanceTests` or the contract tests fail, fix the code. Changing
   a check is a deliberate, reviewed act with justification — never a quiet edit
   to pass CI.

9. **Don't commit data artifacts.**
   Databases, dumps, and archives are git-ignored. A bulk source belongs behind
   `ensure_<db>_db` (downloaded into the user cache), not in the repo. (A *tiny*
   bundled sample like `exampleweaver`'s 5-row CSV is fine.)

See also: [implementing-backends.md](implementing-backends.md) (per-function
contracts) and [../AGENTS.md](../AGENTS.md) (the full boundaries).
