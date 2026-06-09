"""Scaffold generator tests — the round-trip is the headline.

Generate a package from the valid fixture spec, import it, and assert the static
conformance checks pass *by construction*: a freshly-scaffolded weaver's manifest
must already match its spec. This is what lets an agent start from green.
"""

from __future__ import annotations

import asyncio
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
    assert "src/madin_weaver/vocab.py" in names
    assert "src/madin_weaver/weaver.py" in names
    assert "src/madin_weaver/backends/local.py" in names
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
    assert hasattr(mod, "build_madin_weaver")


def test_generated_manifest_matches_spec(tmp_path):
    """The round-trip: scaffold → build → conformance passes with zero edits."""
    spec, dest, _ = _generate(tmp_path)
    mod = _import_generated(dest, spec.package)
    weaver = mod.build_madin_weaver()
    assert check_manifest(weaver.MANIFEST, spec) == []


def test_generated_fingerprints_are_not_unknown(tmp_path):
    spec, dest, _ = _generate(tmp_path)
    mod = _import_generated(dest, spec.package)
    weaver = mod.build_madin_weaver()
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


def test_contributing_doc_generated(tmp_path):
    spec, dest, written = _generate(tmp_path)
    names = {p.relative_to(dest).as_posix() for p in written}
    assert "CONTRIBUTING.md" in names
    text = (dest / "CONTRIBUTING.md").read_text()
    assert f"# Contributing to {spec.package}" in text
    assert "Add an output to an existing capability" in text
    assert "OUTPUT_KEYS" in text  # how to register a new leaf output
    assert "Expansion notes" in text  # the author-filled section
    # spec-aware: lists this weaver's actual produced outputs
    assert "microbe.trait.gram_stain" in text


def test_implementation_worklist_adapts_to_bulk(tmp_path):
    spec = load_spec(BULK_FIXTURE)
    dest = tmp_path / "out"
    scaffold(spec, dest, spec_toml=BULK_FIXTURE.read_text())
    text = (dest / "IMPLEMENTATION.md").read_text()
    assert "Wire the bulk local DB" in text
    assert "setup.py" in text
    assert "bulkdemo_weaver-ensure" in text


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


def test_bulk_pyproject_wires_core_and_script(tmp_path):
    spec, dest = _generate_bulk(tmp_path)
    pyproject = (dest / "pyproject.toml").read_text()
    # Local-DB plumbing (and platformdirs) come from braidworks-core now.
    assert "braidworks-core" in pyproject
    assert "bulkdemo_weaver-ensure" in pyproject
    assert "uv run bulkdemo_weaver-ensure" in (dest / "Makefile").read_text()


def test_bulk_setup_delegates_to_core_localdb(tmp_path):
    spec, dest = _generate_bulk(tmp_path)
    setup = (dest / "src" / spec.package / "setup.py").read_text()
    assert "from braidworks.core.localdb import" in setup
    assert "ensure_local_db" in setup


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


def test_lookup_weaver_is_thin_and_uses_core(tmp_path):
    """Thin model: records/mapper/dispatch/base are NOT generated — imported from core."""
    spec, dest, _ = _generate(tmp_path)
    pkg_dir = dest / "src" / spec.package
    for gone in ("intermediate.py", "mapper.py", "dispatch.py"):
        assert not (pkg_dir / gone).exists(), f"{gone} should no longer be generated"
    assert not (pkg_dir / "backends" / "base.py").exists()
    assert "from braidworks.core import LookupRecord" in (pkg_dir / "backends" / "local.py").read_text()
    assert "map_lookup" in (pkg_dir / "weaver.py").read_text()


def test_resolver_weaver_uses_core_resolver_runtime(tmp_path):
    spec = load_spec(RESOLVER_FIXTURE)
    dest = tmp_path / "out"
    scaffold(spec, dest, spec_toml=RESOLVER_FIXTURE.read_text())
    backend = (dest / "src" / spec.package / "backends" / "local.py").read_text()
    assert "from braidworks.core import Candidate, MatchStatus, ResolverRecord" in backend
    assert "map_resolver" in (dest / "src" / spec.package / "weaver.py").read_text()


def test_resolver_manifest_matches_spec(tmp_path):
    """Resolver scaffold is conformant by construction, same as lookup."""
    spec = load_spec(RESOLVER_FIXTURE)
    dest = tmp_path / "out"
    scaffold(spec, dest, spec_toml=RESOLVER_FIXTURE.read_text())
    mod = _import_generated(dest, spec.package)
    weaver = getattr(mod, f"build_{spec.package}")()
    assert check_manifest(weaver.MANIFEST, spec) == []
    assert check_fingerprints(weaver, list(spec.backends)) == []


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
            c
            for c in classes
            if issubclass(c, CacheFingerprintTests) and c is not CacheFingerprintTests
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


_API_SPEC = """\
[weaver]
db_name = "apidemo"
weaver_id = "apidemo"
kind = "lookup"
title = "API demo weaver"
version = "0.1.0"
license = "CC-BY-4.0"
source_url = "https://example.org/api"
fingerprint_source = "API contract version"
api_key = "{api_key}"
backends = ["local", "api"]
source_sample = "accession,go\\nP12345,GO:1\\n"

[[capability]]
id = "resolve"
consumes = ["protein.uniprot.accession"]

  [[capability.group]]
  id = "g"
  outputs = ["go.term"]
"""


def _generate_api(tmp_path: Path, api_key: str):
    toml = tmp_path / "api.weaver.spec.toml"
    toml.write_text(_API_SPEC.format(api_key=api_key))
    spec = load_spec(toml)
    dest = tmp_path / "out"
    scaffold(spec, dest, spec_toml=toml.read_text())
    return dest / "src" / spec.package / "backends"


def test_api_required_backend_reads_env_and_gates_on_key(tmp_path):
    backends = _generate_api(tmp_path, "required")
    api = (backends / "api.py").read_text()
    # Reads the key from a db-named env var, and is_configured gates on it.
    assert 'API_KEY_ENV = "APIDEMO_API_KEY"' in api
    assert "os.environ.get(API_KEY_ENV)" in api
    assert "return self._api_key is not None" in api
    # The local backend stays the plain (no-key) stub.
    assert "self._configured = False" in (backends / "local.py").read_text()


def test_api_optional_backend_is_configured_without_key(tmp_path):
    backends = _generate_api(tmp_path, "optional")
    api = (backends / "api.py").read_text()
    assert "os.environ.get(API_KEY_ENV)" in api
    assert "return True" in api  # optional: works without the key


def test_api_key_none_uses_plain_stub(tmp_path):
    backends = _generate_api(tmp_path, "none")
    api = (backends / "api.py").read_text()
    # No api_key need -> the api backend gets the plain stub, no env read.
    assert "API_KEY_ENV" not in api
    assert "self._configured = False" in api


_ALWAYS_SPEC = """\
[weaver]
db_name = "acgdemo"
weaver_id = "acgdemo"
kind = "resolver"
title = "always-computed demo"
version = "0.1.0"
license = "CC-BY-4.0"
source_url = "https://example.org/acg"
fingerprint_source = "release-tag"
backends = ["local"]
source_sample = "name,id\\nEscherichia coli,562\\n"

[[capability]]
id = "resolve_name"
consumes = ["organism.name"]
always_computed_groups = ["core"]

  [[capability.group]]
  id = "core"
  outputs = ["ncbi.taxon.id", "organism.scientific_name"]

  [[capability.group]]
  id = "rank"
  outputs = ["ncbi.taxon.rank"]
"""


def test_vocab_puts_always_computed_groups_on_capability(tmp_path):
    """Finding A (thin model): vocab sets always_computed_groups on the core Capability.

    The mapper that unions it into computed_groups now lives in core (covered by
    braidworks-core's test_runtime); here we check the scaffold's half — that the
    spec field reaches the generated manifest.
    """
    toml = tmp_path / "acg.weaver.spec.toml"
    toml.write_text(_ALWAYS_SPEC)
    spec = load_spec(toml)
    dest = tmp_path / "out"
    scaffold(spec, dest, spec_toml=toml.read_text())
    mod = _import_generated(dest, spec.package)
    cap = getattr(mod, f"build_{spec.package}")().MANIFEST.capability("resolve_name")
    assert cap.always_computed_groups == frozenset({"core"})


def test_generated_weaver_wires_core_dispatch(tmp_path):
    """Finding B (thin model): the generated weaver routes through core's dispatch,
    which hands the backend the resolved triggered-group set."""
    from braidworks.core import ResolverRecord, Strand, StrandSet

    spec = load_spec(RESOLVER_FIXTURE)
    dest = tmp_path / "out"
    scaffold(spec, dest, spec_toml=RESOLVER_FIXTURE.read_text())

    src = str(dest / "src")
    sys.path.insert(0, src)
    try:
        importlib.invalidate_caches()
        weaver_mod = importlib.import_module("resolverdemo_weaver.weaver")

        captured: dict[str, frozenset[str]] = {}

        class _CapturingBackend:
            name = "local"

            def is_configured(self):
                return True

            def fingerprint(self):
                return "capture-v1"

            async def fetch(self, capability_id, queries, *, requested_outputs, groups_to_compute):
                captured["groups"] = groups_to_compute
                return [ResolverRecord(query=q) for q in queries]

        weaver = weaver_mod.ResolverdemoWeaver({"local": _CapturingBackend()})
        ss = StrandSet.from_strands("g", [Strand(type_id="organism.name", value="x")])
        # Request only the 'rank' group's output -> triggered groups == {"rank"}.
        asyncio.run(
            weaver.execute(
                "resolve_name",
                ss,
                requested_outputs=frozenset({"ncbi.taxon.rank"}),
                backend="local",
            )
        )
        assert captured["groups"] == frozenset({"rank"})
    finally:
        sys.path.remove(src)
        for name in list(sys.modules):
            if name == "resolverdemo_weaver" or name.startswith("resolverdemo_weaver."):
                del sys.modules[name]
