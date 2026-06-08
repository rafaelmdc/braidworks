# weaverkit

Guardrails for building Braidworks weavers, so an agent can add a database
weaver reliably instead of vibe-coding it. Three pieces:

- **spec** (`weaver.spec.toml`) — the contract an agent fills *before* coding:
  db name, source, license, capabilities (consuming **registered shared keys**),
  output groups, backends, and golden examples. Validated by `weaverkit.spec`.
- **scaffold** (`weaverkit new`) — stamps the deterministic 80% of a weaver
  package from a spec, so the structure/wiring is generated, not hand-written.
- **conformance** (`weaverkit verify` + `WeaverConformanceTests`) — machine checks
  that the built weaver matches its spec, is reachable (consumes a shared key),
  and never returns an `"unknown"` fingerprint.
- **index** (`weaverkit index`) — scans every `weaver.spec.toml` and writes a small
  delimited map (`weaver`, `capability`, `kind`, `api_key`, `backends`, `consumes`,
  `produces`, `unmet_inputs`) so you can see what join keys already exist and pick a
  new weaver's inputs to connect. An `unmet_inputs` entry is a hint, not an error.

The architectural decisions behind the toolkit (what's contract vs weaver freedom,
the `--strict` regimes, dispatcher/backend split) live in
[docs/decisions.md](docs/decisions.md); the resulting work is tracked in
[docs/backlog.md](docs/backlog.md).

When implementing the generated `# TODO` backend spots, see
[docs/implementing-backends.md](docs/implementing-backends.md) — the per-function
contract the stubs deep-link into. For the wider picture see
[docs/weaver-implementation-guide.md](../docs/weaver-implementation-guide.md) and
[AGENTS.md](../AGENTS.md).

## Decision: the spec is TOML, not YAML

The spec format is `weaver.spec.toml`, parsed with the stdlib `tomllib`. This was
a deliberate choice over YAML:

- **No silent type coercion.** A spec is full of short identifiers, version tags,
  and accession-like strings. YAML would mangle them — `license: NO` parses to
  boolean `False` (the "Norway problem"), `version: 1.10` becomes a float and
  drops the trailing zero, `id: 09` can error on octal. TOML keeps every value
  exactly as written. For a *guardrail*, no-surprise parsing matters most.
- **Zero dependencies.** weaverkit is the package everything else trusts; keeping
  it stdlib-only (no PyYAML) is worth more here than anywhere. It also matches the
  rest of the repo — authors are already in `pyproject.toml` headspace.
- **Fails loud, not silent.** TOML errors on malformed structure; YAML often
  parses subtly-wrong input into the wrong shape (merged keys, stray tabs). For an
  agent-authored, machine-validated file, a loud parse error beats a quiet misparse.

The one cost is that the schema is nested (capabilities → groups → outputs), and
TOML's array-of-tables (`[[capability]]`, `[[capability.group]]`) is more verbose
than the YAML equivalent. That's acceptable: the nesting is only two levels deep,
and `validate_spec` turns any structural mistake into a precise error. The spec is
write-once and machine-validated in a loop, so parse-determinism and clear errors
outweigh authoring ergonomics — which is exactly where TOML wins. If this were a
human-tuned config edited daily, YAML would be the better call.
