"""Plain-language diagnostics: did-you-mean, missing sources, workspace install hints."""

from __future__ import annotations

from braidworks.core.capability import Capability, OutputGroup
from braidworks.core.diagnose import (
    explain_no_route,
    suggest_types,
    workspace_weavers,
)
from braidworks.core.registry import BraidRegistry
from tests.helpers import ScriptedWeaver

DOWN_CAP = Capability(
    id="list_structures",
    consumes=frozenset({"protein.uniprot.accession"}),
    produces=frozenset({"pdb.id", "structure.pdb.ids"}),
    output_groups=(OutputGroup(id="g", outputs=frozenset({"pdb.id", "structure.pdb.ids"})),),
    backends=("api",),
)

UNIPROT_SPEC = """
[weaver]
weaver_id = "uniprot"
version = "1.0.0"

[[capability]]
id = "resolve_protein"
consumes = ["protein.query"]
  [[capability.group]]
  id = "identity"
  outputs = ["protein.uniprot.accession", "protein.name"]
"""


def _registry() -> BraidRegistry:
    reg = BraidRegistry()
    reg.register(ScriptedWeaver(lambda *a: None, capability=DOWN_CAP, weaver_id="pdbe"))
    return reg


def _workspace(tmp_path):
    spec_dir = tmp_path / "weavers" / "uniprot_weaver"
    spec_dir.mkdir(parents=True)
    (spec_dir / "weaver.spec.toml").write_text(UNIPROT_SPEC)
    (spec_dir / "pyproject.toml").write_text(
        '[project]\nname = "uniprot-weaver"\n'
        '[project.entry-points."braidworks.weavers"]\nuniprot = "uniprot_weaver:build"\n'
    )
    # a spec without a discoverable package (like the tutorial example) is not offered
    hidden = tmp_path / "weavers" / "example_weaver"
    hidden.mkdir()
    (hidden / "weaver.spec.toml").write_text(UNIPROT_SPEC.replace("uniprot", "example"))
    (hidden / "pyproject.toml").write_text('[project]\nname = "example-weaver"\n')
    (tmp_path / "weavers" / "not_a_weaver").mkdir()
    return tmp_path


def test_suggest_types_handles_typos_and_fragments():
    known = {"protein.name", "protein.query", "structure.pdb.ids", "pdb.id", "gene.symbol"}
    assert suggest_types("protein.nam", known)[0] == "protein.name"
    assert set(suggest_types("pdb", known)) == {"pdb.id", "structure.pdb.ids"}
    assert suggest_types("zzzz", known) == []


def test_workspace_weavers_reads_specs_from_parent_directories(tmp_path):
    root = _workspace(tmp_path)
    nested = root / "some" / "subdir"
    nested.mkdir(parents=True)
    found = workspace_weavers(nested)
    assert [w.weaver_id for w in found] == ["uniprot"]
    assert found[0].package == "uniprot-weaver"
    assert "protein.query" in found[0].consumes
    assert "protein.name" in found[0].produces


def test_workspace_weavers_empty_outside_a_checkout(tmp_path):
    assert workspace_weavers(tmp_path) == []


def test_missing_input_names_the_uninstalled_source(tmp_path):
    lines = explain_no_route(
        _registry(), have={"protein.query"}, want={"structure.pdb.ids"}, start=_workspace(tmp_path)
    )
    text = "\n".join(lines)
    assert "Nothing installed accepts `protein.query`" in text
    assert "uniprot" in text and "not installed" in text
    assert "uv sync --all-extras" in text


def test_unknown_want_suggests_close_names(tmp_path):
    text = "\n".join(
        explain_no_route(
            _registry(), have={"protein.uniprot.accession"}, want={"pdb"}, start=tmp_path
        )
    )
    assert "No installed source provides `pdb`" in text
    assert "structure.pdb.ids" in text and "pdb.id" in text


def test_unknown_types_without_hints_point_to_keys(tmp_path):
    text = "\n".join(explain_no_route(_registry(), have={"a.b"}, want={"zzzz"}, start=tmp_path))
    assert "braidworks keys" in text


def test_never_suggests_the_type_itself(tmp_path):
    # pdb.id exists, but only as an output; suggesting `pdb.id` back would be noise
    text = "\n".join(
        explain_no_route(_registry(), have={"pdb.id"}, want={"structure.pdb.ids"}, start=tmp_path)
    )
    assert "Nothing installed accepts `pdb.id`" in text
    assert "`pdb.id`?" not in text


def test_known_but_disconnected_types_point_to_path(tmp_path):
    gene_cap = Capability(
        id="describe_gene",
        consumes=frozenset({"gene.id"}),
        produces=frozenset({"gene.name"}),
        output_groups=(OutputGroup(id="g", outputs=frozenset({"gene.name"})),),
        backends=("api",),
    )
    reg = _registry()
    reg.register(ScriptedWeaver(lambda *a: None, capability=gene_cap, weaver_id="genes"))
    text = "\n".join(
        explain_no_route(
            reg, have={"protein.uniprot.accession"}, want={"gene.name"}, start=tmp_path
        )
    )
    assert "cannot connect" in text
    assert "braidworks path --from protein.uniprot.accession --to gene.name" in text
