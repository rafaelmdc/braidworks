# Implementing mondo_weaver

Generated worklist — do these in order. Each step maps to `# TODO` markers in
the code. **Definition of done:**

```bash
make test
weaverkit verify --spec weaver.spec.toml --package mondo_weaver --strict
```

Per-function contracts: [../../weaverkit/docs/implementing-backends.md](../../weaverkit/docs/implementing-backends.md).  
Common mistakes: [../../weaverkit/docs/PITFALLS.md](../../weaverkit/docs/PITFALLS.md).  
Worked example to copy: `../example_weaver/src/example_weaver/backends/local.py`.

## 1. Implement the backend(s)

- [ ] `src/mondo_weaver/backends/local.py` — fill `is_configured`, `fingerprint`, and `fetch` ([#fingerprint](../../weaverkit/docs/implementing-backends.md#fingerprint), [#fetch](../../weaverkit/docs/implementing-backends.md#fetch))

## 2. Verify (definition of done)

- [ ] `make test` — conformance + contract + golden all green
- [ ] `weaverkit verify --spec weaver.spec.toml --package mondo_weaver --strict` — no placeholders left, golden runs
- [ ] register the weaver where the app assembles its `WeaverFactory` (see README)
- [ ] after merge, tag the release `mondo_weaver-v0.1.0` — `make tags` does this for every bumped package (CI also auto-tags on merge to main)
