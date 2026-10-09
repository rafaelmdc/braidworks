# Extending an implemented weaver safely

Scaffolding creates an entire package, including placeholder backends, factories
and tests. `new --force` replaces those generated paths; it does not merge local
implementation. Use it only for disposable scaffold output.

From the implemented package directory, edit the spec and run:

```bash
scratch_dir=$(mktemp -d)
weaverkit new --spec weaver.spec.toml --dest "$scratch_dir/package"
diff -ru --exclude=.git --exclude=__pycache__ --exclude=.pytest_cache . "$scratch_dir/package"
```

`diff` exits 1 when differences exist. Review changes; do not treat the scaffold’s
placeholder backend as an implementation update. Selectively copy the generated
`src/<package>/vocab.py`. Merge new backend/capability wiring into existing code,
keep configured builders, tests, provenance policies and contributor notes, and
update all three version sites when behavior changes. Validate the spec, run the
package suite and `weaverkit verify --spec weaver.spec.toml --package <package>
--strict`, then inspect the final git diff and remove your scratch directory.

NCBI is handwritten and contains custom vocab constants. Edit its vocab manually;
scaffold vocab is not a safe replacement. Initial scaffolding still follows the
Spec → Scaffold → Implement → Verify loop in the repository AGENTS.md.
