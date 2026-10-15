"""Generated inventory ownership, drift checks and scaffold integration."""

from dataclasses import replace
from pathlib import Path

import pytest
from weaverkit.capability_docs import (
    END,
    START,
    render_capabilities,
    replace_inventory,
    update_capability_docs,
)
from weaverkit.cli import main
from weaverkit.scaffold import generate_files
from weaverkit.spec import load_spec

FIXTURE = Path(__file__).parent / "fixtures" / "valid.weaver.spec.toml"


def test_render_and_replace_preserves_prose_and_is_idempotent():
    spec = load_spec(FIXTURE)
    original = "Purpose and workflow\n" + START + "\nstale\n" + END + "\nSource caveats\n"
    updated = replace_inventory(original, spec)
    assert updated.startswith("Purpose and workflow\n")
    assert updated.endswith("\nSource caveats\n")
    assert "resolve_traits" in updated and "traits.growth" in updated
    assert replace_inventory(updated, spec) == updated


@pytest.mark.parametrize("document", ["", START, END + START, START + START + END])
def test_malformed_ownership_fails(document):
    with pytest.raises(ValueError):
        replace_inventory(document, load_spec(FIXTURE))


def test_alternative_inputs_and_per_capability_backends():
    spec = load_spec(FIXTURE)
    cap = replace(
        spec.capabilities[0],
        consumes=("a", "b"),
        consumes_any=True,
        backends=("api",),
        set_outputs=("x",),
    )
    text = render_capabilities(replace(spec, backends=("local", "api"), capabilities=(cap,)))
    assert "`a` or `b`" in text and "; expands `x`" in text
    assert "| `api` |" in text


def _package(root, name):
    package = root / "weavers" / name
    package.mkdir(parents=True)
    (package / "weaver.spec.toml").write_text(FIXTURE.read_text())
    doc = package / "REFERENCE.md"
    doc.write_text("Keep this explanation\n" + START + "\nstale\n" + END + "\n")
    return doc


def test_check_reports_drift_without_writing_then_update_cleans_it(tmp_path):
    doc = _package(tmp_path, "one")
    original = doc.read_text()
    assert main(["capability-docs", "--root", str(tmp_path), "--check"]) == 1
    assert doc.read_text() == original
    assert main(["capability-docs", "--root", str(tmp_path)]) == 0
    assert "Keep this explanation" in doc.read_text()
    assert main(["capability-docs", "--root", str(tmp_path), "--check"]) == 0


def test_invalid_later_package_prevents_partial_update(tmp_path):
    first = _package(tmp_path, "a")
    original = first.read_text()
    second = _package(tmp_path, "b")
    second.write_text("unmarked")
    with pytest.raises(ValueError):
        update_capability_docs(tmp_path)
    assert first.read_text() == original


def test_scaffold_inventory_matches_generator(tmp_path):
    spec = load_spec(FIXTURE)
    artifacts = generate_files(spec, spec_toml=FIXTURE.read_text())
    readme = artifacts[Path("README.md")]
    assert render_capabilities(spec) in readme
    assert replace_inventory(readme, spec) == readme


def test_empty_root_fails_instead_of_claiming_freshness(tmp_path):
    assert main(["capability-docs", "--root", str(tmp_path), "--check"]) == 1
