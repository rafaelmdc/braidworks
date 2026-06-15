"""Tests for the ``braidworks`` CLI — offline, against a tiny two-weaver registry.

The CLI normally discovers weavers from entry points; here we monkeypatch the
discovery hook to a fixed registry (a `resolve` weaver feeding a `describe` weaver)
so every command — weave/run/weavers/keys/path/references — is exercised without a
network. Output is captured via capsys; data goes to stdout, progress to stderr.
"""

from __future__ import annotations

import json

import pytest

from braidworks.core import cli
from braidworks.core.capability import (
    Capability,
    OutputGroup,
    Parameter,
    Provenance,
    WeaverManifest,
)
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import Strand

from tests.helpers import ScriptedWeaver

# --- a fixed, offline two-weaver network -------------------------------------------

UP_CAP = Capability(
    id="resolve_protein",
    consumes=frozenset({"protein.query"}),
    produces=frozenset({"protein.uniprot.accession", "protein.name"}),
    output_groups=(OutputGroup(id="g", outputs=frozenset(
        {"protein.uniprot.accession", "protein.name"})),),
    backends=("api",),
)
DOWN_CAP = Capability(
    id="list_structures",
    consumes=frozenset({"protein.uniprot.accession"}),
    produces=frozenset({"pdb.id", "structure.pdb.ids"}),
    output_groups=(OutputGroup(id="g", outputs=frozenset({"pdb.id", "structure.pdb.ids"})),),
    set_outputs=frozenset({"pdb.id"}),
    parameters=(Parameter("level", enum=("all", "best"), default="all",
                          description="how many structures"),),
    backends=("api",),
)


def _up_resolver(ss, backend, requested):
    q = ss.get("protein.query").value
    if q == "MISS":
        return WeaveResult("resolve_protein", "1.0.0", backend, frozenset({"g"}),
                           status=WeaveStatus.NO_MATCH)
    return WeaveResult(
        "resolve_protein", "1.0.0", backend, frozenset({"g"}), status=WeaveStatus.OK,
        strands=(Strand("protein.uniprot.accession", f"ACC_{q}"),
                 Strand("protein.name", f"Name of {q}")),
    )


def _down_resolver(ss, backend, requested):
    acc = ss.get("protein.uniprot.accession").value
    ids = [f"{acc}-1", f"{acc}-2"]
    return WeaveResult(
        "list_structures", "1.0.0", backend, frozenset({"g"}), status=WeaveStatus.OK,
        strands=(Strand("pdb.id", ids), Strand("structure.pdb.ids", ids)),
    )


def _make_registry(*, only=None) -> BraidRegistry:
    reg = BraidRegistry()
    weavers = {
        "uniprot": ScriptedWeaver(_up_resolver, capability=UP_CAP, weaver_id="uniprot"),
        "pdbe": ScriptedWeaver(_down_resolver, capability=DOWN_CAP, weaver_id="pdbe"),
    }
    # give one weaver provenance so `references` has something to print
    weavers["pdbe"]._manifest = WeaverManifest(
        weaver_id="pdbe", version="1.0.0", capabilities=(DOWN_CAP,),
        provenance=Provenance(source_url="https://pdbe.test", license="CC0-1.0",
                              citation="doi:test", attribution="PDBe"),
    )
    for name, w in weavers.items():
        if only is None or name in only:
            reg.register(w)
    return reg


@pytest.fixture(autouse=True)
def _patch_discovery(monkeypatch):
    monkeypatch.setattr(cli, "build_registry_from_entry_points", _make_registry)


def _run(*argv):
    return cli.main(list(argv))


# --- weave -------------------------------------------------------------------------

def test_weave_human_resolves_and_prints(capsys):
    code = _run("weave", "--have", "protein.query=P1", "--want", "protein.name")
    out = capsys.readouterr()
    assert code == 0
    assert "protein.name: Name of P1" in out.out
    assert "1 resolved" in out.err  # summary on stderr


def test_weave_chains_two_weavers(capsys):
    code = _run("weave", "--have", "protein.query=P1", "--want", "structure.pdb.ids")
    out = capsys.readouterr().out
    assert code == 0
    assert "ACC_P1-1" in out  # came through uniprot -> pdbe


def test_weave_json_format(capsys):
    _run("weave", "--have", "protein.query=P1", "--want", "protein.name", "--format", "json")
    data = json.loads(capsys.readouterr().out)
    assert data[0]["entity"] == "e1"
    assert data[0]["values"]["protein.name"] == "Name of P1"


def test_weave_tsv_format(capsys):
    _run("weave", "--have", "protein.query=P1", "--want", "protein.name", "--format", "tsv")
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0].split("\t") == ["entity", "protein.name"]
    assert lines[1].split("\t") == ["e1", "Name of P1"]


def test_weave_batch_one_per_line(tmp_path, capsys):
    f = tmp_path / "ids.txt"
    f.write_text("P1\n# comment\n\nP2\n")
    _run("weave", "--in-file", str(f), "--in-type", "protein.query",
         "--want", "protein.name", "--format", "jsonl")
    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert [r["entity"] for r in lines] == ["P1", "P2"]  # entity id = the value


def test_weave_batch_tsv_table(tmp_path, capsys):
    f = tmp_path / "in.tsv"
    f.write_text("protein.query\nP1\nP2\n")
    _run("weave", "--in-file", str(f), "--want", "protein.name", "--format", "tsv")
    rows = capsys.readouterr().out.strip().splitlines()
    assert len(rows) == 3  # header + 2


def test_weave_fanout_expands_children(capsys):
    _run("weave", "--have", "protein.query=P1", "--want", "structure.pdb.ids",
         "--expand", "all", "--format", "jsonl")
    recs = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert len(recs) == 2  # two pdb.id children
    assert all(r.get("parent") == "e1" for r in recs)


def test_weave_unresolved_is_reported(capsys):
    code = _run("weave", "--have", "protein.query=MISS", "--want", "protein.name")
    out = capsys.readouterr()
    assert code == 0  # NO_MATCH is valid data, not an error
    assert "1 unresolved" in out.err


def test_weave_strict_exits_nonzero_on_unresolved(capsys):
    code = _run("weave", "--have", "protein.query=MISS", "--want", "protein.name", "--strict")
    assert code == 1


def test_weave_no_route_is_friendly_error(capsys):
    code = _run("weave", "--have", "x.y=z", "--want", "no.such.type")
    assert code == 1
    assert "no route" in capsys.readouterr().err


def test_weave_requires_want():
    with pytest.raises(SystemExit):
        _run("weave", "--have", "protein.query=P1")


# --- run ---------------------------------------------------------------------------

def test_run_single_capability(capsys):
    code = _run("run", "uniprot", "resolve_protein", "--have", "protein.query=P1",
                "--want", "protein.name")
    assert code == 0
    assert "Name of P1" in capsys.readouterr().out


def test_run_infers_sole_backend(capsys):
    code = _run("run", "pdbe", "list_structures", "--have", "protein.uniprot.accession=ACC_X")
    assert code == 0
    assert "ACC_X-1" in capsys.readouterr().out


def test_run_unknown_capability_errors(capsys):
    code = _run("run", "uniprot", "nope", "--have", "protein.query=P1")
    assert code == 1
    assert "no capability" in capsys.readouterr().err


# --- inspect commands --------------------------------------------------------------

def test_weavers_lists_capabilities(capsys):
    _run("weavers")
    out = capsys.readouterr().out
    assert "uniprot" in out and "resolve_protein" in out
    assert "⤜ fan: pdb.id" in out  # set_outputs surfaced


def test_weavers_json(capsys):
    _run("weavers", "--format", "json")
    data = {m["weaver"]: m for m in json.loads(capsys.readouterr().out)}
    assert data["pdbe"]["capabilities"][0]["set_outputs"] == ["pdb.id"]


def test_keys_shows_producers_and_consumers(capsys):
    _run("keys", "--produces", "protein.uniprot.accession")
    out = capsys.readouterr().out
    assert "produced by: uniprot.resolve_protein" in out
    assert "consumed by: pdbe.list_structures" in out


def test_path_shows_route(capsys):
    code = _run("path", "--from", "protein.query", "--to", "structure.pdb.ids")
    out = capsys.readouterr().out
    assert code == 0
    assert "uniprot.resolve_protein" in out and "pdbe.list_structures" in out
    assert "2 step(s)" in out


def test_path_no_route(capsys):
    code = _run("path", "--from", "protein.query", "--to", "no.such")
    assert code == 1


def test_references(capsys):
    _run("references")
    assert "PDBe" in capsys.readouterr().out


def test_only_restricts_registry(capsys):
    # with only uniprot loaded, there's no route to a pdbe-only output
    code = _run("weave", "--have", "protein.query=P1", "--want", "structure.pdb.ids",
                "--only", "uniprot")
    assert code == 1


# --- parsing helpers ---------------------------------------------------------------

def test_expand_policy_parsing():
    from braidworks.core.executor import ExpandMode
    assert cli._expand_policy("none").mode is ExpandMode.TOP
    assert cli._expand_policy("all").mode is ExpandMode.ALL
    assert cli._expand_policy("top:3").k == 3
    with pytest.raises(SystemExit):
        cli._expand_policy("bogus")


def test_parse_kv_requires_equals():
    with pytest.raises(SystemExit):
        cli._parse_kv("novalue")


# --- parameters --------------------------------------------------------------------

def test_weavers_lists_parameters(capsys):
    _run("weavers")
    out = capsys.readouterr().out
    assert "--param level" in out and "best" in out  # enum surfaced


def test_weavers_json_includes_parameters(capsys):
    _run("weavers", "--format", "json")
    data = {m["weaver"]: m for m in json.loads(capsys.readouterr().out)}
    params = data["pdbe"]["capabilities"][0]["parameters"]
    assert params[0]["name"] == "level" and params[0]["enum"] == ["all", "best"]


def test_weave_accepts_valid_param(capsys):
    code = _run("weave", "--have", "protein.query=P1", "--want", "structure.pdb.ids",
                "--param", "level=best")
    assert code == 0
    assert "ACC_P1-1" in capsys.readouterr().out


def test_weave_rejects_param_outside_enum(capsys):
    code = _run("weave", "--have", "protein.query=P1", "--want", "structure.pdb.ids",
                "--param", "level=nope")
    assert code == 1
    assert "not in allowed values" in capsys.readouterr().err


def test_weave_rejects_unknown_param_name(capsys):
    code = _run("weave", "--have", "protein.query=P1", "--want", "structure.pdb.ids",
                "--param", "bogus=1")
    assert code == 1
    assert "no step in this route accepts" in capsys.readouterr().err


def test_run_accepts_param(capsys):
    code = _run("run", "pdbe", "list_structures",
                "--have", "protein.uniprot.accession=ACC_X", "--param", "level=best")
    assert code == 0


# --- traversal fan-out (--for-each / --traverse) -----------------------------------

def test_for_each_fans_through_relationship(capsys):
    # 'structures' = list_structures (a fan capability) minus the list_ prefix.
    code = _run("weave", "--have", "protein.uniprot.accession=ACC_X",
                "--for-each", "structures", "--format", "json")
    out = capsys.readouterr()
    assert code == 0
    records = json.loads(out.out)
    # one child per fanned pdb.id, each re-rooted (parent = original entity), all regroup
    assert len(records) == 2
    assert {r["parent"] for r in records} == {"e1"}
    assert sorted(r["values"]["pdb.id"] for r in records) == ["ACC_X-1", "ACC_X-2"]


def test_traverse_accepts_capability_id(capsys):
    code = _run("weave", "--have", "protein.uniprot.accession=ACC_X",
                "--traverse", "list_structures", "--format", "json")
    assert code == 0
    assert len(json.loads(capsys.readouterr().out)) == 2


def test_for_each_unknown_relationship_errors(capsys):
    code = _run("weave", "--have", "protein.uniprot.accession=ACC_X", "--for-each", "bogus")
    assert code == 1
    assert "no traversal" in capsys.readouterr().err


# --- structural errors are reported, not silent -------------------------------------

def test_weave_reports_structural_error_and_exits_nonzero(monkeypatch, capsys):
    """A node that 5xx's must not vanish into an empty result with exit 0."""
    boom_cap = Capability(
        id="boom", consumes=frozenset({"protein.query"}),
        produces=frozenset({"protein.name"}),
        output_groups=(OutputGroup(id="g", outputs=frozenset({"protein.name"})),),
        backends=("api",))

    def boom(ss, b, r):
        return WeaveResult("boom", "1.0.0", b, frozenset({"g"}),
                           status=WeaveStatus.ERROR, errors=("Server error '503'",))

    reg = BraidRegistry()
    reg.register(ScriptedWeaver(boom, capability=boom_cap, weaver_id="boomw"))
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: reg)

    code = _run("weave", "--have", "protein.query=X", "--want", "protein.name")
    err = capsys.readouterr().err
    assert code == 1  # fatal structural error → non-zero (was: silent exit 0)
    assert "error(s)" in err
    assert "unavailable" in err  # the plain-English category explanation


def test_run_rejects_bad_param(capsys):
    code = _run("run", "pdbe", "list_structures",
                "--have", "protein.uniprot.accession=ACC_X", "--param", "level=nope")
    assert code == 1
    assert "not in allowed values" in capsys.readouterr().err


def test_parse_params_forms():
    assert cli._parse_params(["a=1", "cap:b=2"]) == [(None, "a", "1"), ("cap", "b", "2")]
    with pytest.raises(SystemExit):
        cli._parse_params(["noequals"])
