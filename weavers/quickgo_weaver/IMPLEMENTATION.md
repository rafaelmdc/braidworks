# Implementing quickgo_weaver

Generated worklist — do these in order. Each step maps to `# TODO` markers in
the code. **Definition of done:**

```bash
make test
weaverkit verify --spec weaver.spec.toml --package quickgo_weaver --strict
```

Per-function contracts: [../../weaverkit/docs/implementing-backends.md](../../weaverkit/docs/implementing-backends.md).  
Common mistakes: [../../weaverkit/docs/PITFALLS.md](../../weaverkit/docs/PITFALLS.md).  
Worked example to copy: `../example_weaver/src/example_weaver/backends/local.py`.

## 1. Implement the backend(s)

- [ ] `src/quickgo_weaver/backends/api.py` — fill `is_configured`, `fingerprint`, and `fetch` ([#fingerprint](../../weaverkit/docs/implementing-backends.md#fingerprint), [#fetch](../../weaverkit/docs/implementing-backends.md#fetch))

## 2. Keep the api tests offline (the fixture)

- [ ] fill `src/quickgo_weaver/fixture.py` `_handler` with canned responses your `fetch` parses (an `httpx.MockTransport`, no network).
- [ ] a keyless API is *always configured*, so once your `fetch` works the generated golden/order tests stop skipping and would hit the live service. Point `tests/test_conformance.py`'s `build_weaver` and `tests/test_contract.py`'s `make_weaver` at `build_quickgo_weaver_fixture()` so they run offline (the manifest/fingerprint are identical to the live build).
- [ ] fill `tests/test_e2e_live.py` with a known-truth example; run it with `make test-live` (`BRAIDWORKS_RUN_LIVE=1`) after api-touching changes.

## 3. Verify (definition of done)

- [ ] `make test` — conformance + contract + golden all green
- [ ] `weaverkit verify --spec weaver.spec.toml --package quickgo_weaver --strict` — no placeholders left, golden runs
- [ ] register the weaver where the app assembles its `WeaverFactory` (see README)
