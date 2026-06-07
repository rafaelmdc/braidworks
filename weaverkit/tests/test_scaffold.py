"""Scaffold generator tests — the round-trip is the headline.

Generate a package from the valid fixture spec, import it, and assert the static
conformance checks pass *by construction*: a freshly-scaffolded weaver's manifest
must already match its spec. This is what lets an agent start from green.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from weaverkit.conformance import check_fingerprints, check_manifest
from weaverkit.scaffold import ScaffoldError, scaffold
from weaverkit.spec import load_spec

FIXTURE = Path(__file__).parent / "fixtures" / "valid.weaver.spec.toml"


def _generate(tmp_path: Path):
    spec = load_spec(FIXTURE)
    dest = tmp_path / "out"
    written = scaffold(spec, dest, spec_toml=FIXTURE.read_text())
    return spec, dest, written


def test_scaffold_writes_expected_files(tmp_path):
    spec, dest, written = _generate(tmp_path)
    names = {p.relative_to(dest).as_posix() for p in written}
    assert "pyproject.toml" in names
    assert "weaver.spec.toml" in names
    assert "src/madinweaver/vocab.py" in names
    assert "src/madinweaver/weaver.py" in names
    assert "src/madinweaver/backends/local.py" in names
    assert "tests/test_conformance.py" in names


def test_scaffold_refuses_nonempty_dest(tmp_path):
    spec = load_spec(FIXTURE)
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "stuff.txt").write_text("x")
    with pytest.raises(ScaffoldError):
        scaffold(spec, dest, spec_toml=FIXTURE.read_text())


def test_scaffold_force_overwrites(tmp_path):
    spec = load_spec(FIXTURE)
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "stuff.txt").write_text("x")
    written = scaffold(spec, dest, spec_toml=FIXTURE.read_text(), force=True)
    assert written


def test_copied_spec_is_verbatim(tmp_path):
    spec, dest, _ = _generate(tmp_path)
    assert (dest / "weaver.spec.toml").read_text() == FIXTURE.read_text()


def _import_generated(dest: Path, pkg: str):
    """Import a generated package from its src/ dir, isolating sys.path/modules."""
    src = str(dest / "src")
    sys.path.insert(0, src)
    # Drop any cached submodules from a previous generation in the same process.
    for name in list(sys.modules):
        if name == pkg or name.startswith(pkg + "."):
            del sys.modules[name]
    try:
        return importlib.import_module(pkg)
    finally:
        sys.path.remove(src)


def test_generated_package_imports(tmp_path):
    spec, dest, _ = _generate(tmp_path)
    mod = _import_generated(dest, spec.package)
    assert hasattr(mod, "build_madinweaver")


def test_generated_manifest_matches_spec(tmp_path):
    """The round-trip: scaffold → build → conformance passes with zero edits."""
    spec, dest, _ = _generate(tmp_path)
    mod = _import_generated(dest, spec.package)
    weaver = mod.build_madinweaver()
    assert check_manifest(weaver.MANIFEST, spec) == []


def test_generated_fingerprints_are_not_unknown(tmp_path):
    spec, dest, _ = _generate(tmp_path)
    mod = _import_generated(dest, spec.package)
    weaver = mod.build_madinweaver()
    # Placeholder fingerprints are TODO but must already be valid (not '' / 'unknown').
    assert check_fingerprints(weaver, list(spec.backends)) == []


def test_generated_register_wires_into_factory(tmp_path):
    from braidworks.core import WeaverFactory

    spec, dest, _ = _generate(tmp_path)
    mod = _import_generated(dest, spec.package)
    factory = WeaverFactory()
    mod.register(factory)
    assert spec.resolved_weaver_id in factory.providers()


RESOLVER_FIXTURE = Path(__file__).parent / "fixtures" / "resolver.weaver.spec.toml"
BULK_FIXTURE = Path(__file__).parent / "fixtures" / "bulk.weaver.spec.toml"


def test_implementation_worklist_generated(tmp_path):
    spec, dest, written = _generate(tmp_path)
    names = {p.relative_to(dest).as_posix() for p in written}
    assert "IMPLEMENTATION.md" in names
    text = (dest / "IMPLEMENTATION.md").read_text()
    # mentions each backend file and ends at the strict definition-of-done
    for b in spec.backends:
        assert f"src/{spec.package}/backends/{b}.py" in text
    assert "--strict" in text
    assert "make test" in text


def test_implementation_worklist_adapts_to_bulk(tmp_path):
    spec = load_spec(BULK_FIXTURE)
    dest = tmp_path / "out"
    scaffold(spec, dest, spec_toml=BULK_FIXTURE.read_text())
    text = (dest / "IMPLEMENTATION.md").read_text()
    assert "Wire the bulk local DB" in text
    assert "setup.py" in text
    assert "bulkdemoweaver-ensure" in text


def test_lookup_scaffold_has_no_setup(tmp_path):
    spec, dest, written = _generate(tmp_path)
    names = {p.relative_to(dest).as_posix() for p in written}
    assert f"src/{spec.package}/setup.py" not in names
    assert f"src/{spec.package}/ensure.py" not in names
    assert '"platformdirs' not in (dest / "pyproject.toml").read_text()


def _generate_bulk(tmp_path):
    spec = load_spec(BULK_FIXTURE)
    dest = tmp_path / "out"
    scaffold(spec, dest, spec_toml=BULK_FIXTURE.read_text())
    return spec, dest


def test_bulk_scaffold_emits_setup_and_ensure(tmp_path):
    spec, dest = _generate_bulk(tmp_path)
    assert (dest / "src" / spec.package / "setup.py").exists()
    assert (dest / "src" / spec.package / "ensure.py").exists()
    setup = (dest / "src" / spec.package / "setup.py").read_text()
    assert "def ensure_bulkdemo_db" in setup
    assert "def default_db_path" in setup


def test_bulk_pyproject_wires_platformdirs_and_script(tmp_path):
    spec, dest = _generate_bulk(tmp_path)
    pyproject = (dest / "pyproject.toml").read_text()
    assert "platformdirs" in pyproject
    assert "bulkdemoweaver-ensure" in pyproject
    assert "uv run bulkdemoweaver-ensure" in (dest / "Makefile").read_text()


def test_bulk_backend_uses_default_db_path(tmp_path):
    spec, dest = _generate_bulk(tmp_path)
    local = (dest / "src" / spec.package / "backends" / "local.py").read_text()
    assert "default_db_path" in local
    assert "db_is_valid" in local


def test_bulk_manifest_conformant_and_compiles(tmp_path):
    spec, dest = _generate_bulk(tmp_path)
    for name in ("setup.py", "ensure.py", "backends/local.py"):
        compile((dest / "src" / spec.package / name).read_text(), name, "exec")
    mod = _import_generated(dest, spec.package)
    weaver = getattr(mod, f"build_{spec.package}")()
    assert check_manifest(weaver.MANIFEST, spec) == []
    assert check_fingerprints(weaver, list(spec.backends)) == []


def test_lookup_intermediate_is_flat(tmp_path):
    spec, dest, _ = _generate(tmp_path)
    text = (dest / "src" / spec.package / "intermediate.py").read_text()
    assert "MatchStatus" not in text
    assert "found: bool" in text


def test_resolver_generates_match_status_and_candidates(tmp_path):
    spec = load_spec(RESOLVER_FIXTURE)
    dest = tmp_path / "out"
    scaffold(spec, dest, spec_toml=RESOLVER_FIXTURE.read_text())
    inter = (dest / "src" / spec.package / "intermediate.py").read_text()
    mapper = (dest / "src" / spec.package / "mapper.py").read_text()
    assert "class MatchStatus" in inter
    assert "class Candidate" in inter
    assert "WeaveStatus.AMBIGUOUS" in mapper
    assert "CandidateResult" in mapper
    assert "requires_review" in mapper


def test_resolver_manifest_matches_spec(tmp_path):
    """Resolver scaffold is conformant by construction, same as lookup."""
    spec = load_spec(RESOLVER_FIXTURE)
    dest = tmp_path / "out"
    scaffold(spec, dest, spec_toml=RESOLVER_FIXTURE.read_text())
    mod = _import_generated(dest, spec.package)
    weaver = getattr(mod, f"build_{spec.package}")()
    assert check_manifest(weaver.MANIFEST, spec) == []
    assert check_fingerprints(weaver, list(spec.backends)) == []


def test_resolver_intermediate_and_mapper_compile(tmp_path):
    spec = load_spec(RESOLVER_FIXTURE)
    dest = tmp_path / "out"
    scaffold(spec, dest, spec_toml=RESOLVER_FIXTURE.read_text())
    for name in ("intermediate.py", "mapper.py"):
        source = (dest / "src" / spec.package / name).read_text()
        compile(source, name, "exec")


def test_generated_vocab_is_valid_python(tmp_path):
    spec, dest, _ = _generate(tmp_path)
    source = (dest / "src" / spec.package / "vocab.py").read_text()
    compile(source, "vocab.py", "exec")  # must parse


# Anchors the generated backend TODOs deep-link into implementing-backends.md.
# If a heading is renamed, the links rot silently — this test catches that.
_DOC = Path(__file__).resolve().parents[1] / "docs" / "implementing-backends.md"
_TODO_ANCHORS = ("is_configured", "fingerprint", "fetch")


def test_backend_doc_exists_with_referenced_anchors():
    text = _DOC.read_text()
    headings = {
        line[3:].strip().lower().replace(" ", "-")
        for line in text.splitlines()
        if line.startswith("## ")
    }
    for anchor in _TODO_ANCHORS:
        assert anchor in headings, f"implementing-backends.md is missing #{anchor}"


def test_generated_backend_links_to_doc_anchors(tmp_path):
    spec, dest, _ = _generate(tmp_path)
    stub = (dest / "src" / spec.package / "backends" / "local.py").read_text()
    assert "implementing-backends.md" in stub
    for anchor in _TODO_ANCHORS:
        assert f"implementing-backends.md#{anchor}" in stub


def _load_module_from(path: Path, name: str):
    import importlib.util

    loader = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    return module


def test_generated_contract_tests_pass_on_fresh_scaffold(tmp_path):
    """The pure contract tests must be green by construction; execute-tests skip.

    Loads the generated test_contract.py and runs the cache-fingerprint tests
    (which need no data) plus the sample-distinctness check — proving a fresh
    scaffold ships a passing contract suite, not a red one.
    """
    from braidworks.testing.contract import CacheFingerprintTests, WeaverOrderContractTests

    spec, dest, _ = _generate(tmp_path)
    src = str(dest / "src")
    sys.path.insert(0, src)
    for mod_name in list(sys.modules):
        if mod_name == spec.package or mod_name.startswith(spec.package + "."):
            del sys.modules[mod_name]
    try:
        importlib.invalidate_caches()
        mod = _load_module_from(dest / "tests" / "test_contract.py", "gen_test_contract")
        classes = [c for c in vars(mod).values() if isinstance(c, type)]

        cache_classes = [
            c for c in classes if issubclass(c, CacheFingerprintTests) and c is not CacheFingerprintTests
        ]
        assert cache_classes, "expected a generated CacheFingerprintTests subclass"
        ran = 0
        for cls in cache_classes:
            inst = cls()
            for name in dir(inst):
                if name.startswith("test_"):
                    getattr(inst, name)()  # raises on failure
                    ran += 1
        assert ran >= 5

        order_classes = [
            c
            for c in classes
            if issubclass(c, WeaverOrderContractTests) and c is not WeaverOrderContractTests
        ]
        assert order_classes, "expected a generated WeaverOrderContractTests subclass"
        for cls in order_classes:
            cls().test_at_least_five_distinct_samples()  # seeded inputs are >=5 distinct
    finally:
        sys.path.remove(src)
        sys.modules.pop("gen_test_contract", None)
        for mod_name in list(sys.modules):
            if mod_name == spec.package or mod_name.startswith(spec.package + "."):
                del sys.modules[mod_name]
