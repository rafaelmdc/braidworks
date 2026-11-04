"""Tests for the ``braidworks`` CLI — offline, against a tiny two-weaver registry.

The CLI normally discovers weavers from entry points; here we monkeypatch the
discovery hook to a fixed registry (a `resolve` weaver feeding a `describe` weaver)
so every command — weave/run/weavers/keys/path/references — is exercised without a
network. Output is captured via capsys; data goes to stdout, progress to stderr.
"""

from __future__ import annotations

import csv
import io
import json
import subprocess
import sys

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
    output_groups=(
        OutputGroup(id="g", outputs=frozenset({"protein.uniprot.accession", "protein.name"})),
    ),
    backends=("api",),
)
DOWN_CAP = Capability(
    id="list_structures",
    consumes=frozenset({"protein.uniprot.accession"}),
    produces=frozenset({"pdb.id", "structure.pdb.ids"}),
    output_groups=(OutputGroup(id="g", outputs=frozenset({"pdb.id", "structure.pdb.ids"})),),
    set_outputs=frozenset({"pdb.id"}),
    parameters=(
        Parameter("level", enum=("all", "best"), default="all", description="how many structures"),
    ),
    backends=("api",),
)


def _up_resolver(ss, backend, requested):
    q = ss.get("protein.query").value
    if q == "MISS":
        return WeaveResult(
            "resolve_protein", "1.0.0", backend, frozenset({"g"}), status=WeaveStatus.NO_MATCH
        )
    return WeaveResult(
        "resolve_protein",
        "1.0.0",
        backend,
        frozenset({"g"}),
        status=WeaveStatus.OK,
        strands=(
            Strand("protein.uniprot.accession", f"ACC_{q}"),
            Strand("protein.name", f"Name of {q}"),
        ),
    )


def _down_resolver(ss, backend, requested):
    acc = ss.get("protein.uniprot.accession").value
    ids = [f"{acc}-1", f"{acc}-2"]
    return WeaveResult(
        "list_structures",
        "1.0.0",
        backend,
        frozenset({"g"}),
        status=WeaveStatus.OK,
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
        weaver_id="pdbe",
        version="1.0.0",
        capabilities=(DOWN_CAP,),
        provenance=Provenance(
            source_url="https://pdbe.test",
            license="CC0-1.0",
            citation="doi:test",
            attribution="PDBe",
        ),
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
    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out), delimiter="\t"))
    assert rows[0]["entity"] == "e1"
    assert rows[0]["status"] == "resolved"
    assert rows[0]["protein.name"] == "Name of P1"


@pytest.mark.parametrize("fmt", ["json", "tsv", "csv"])
@pytest.mark.parametrize("command", ["run", "weave"])
def test_exports_include_every_terminal_outcome(tmp_path, monkeypatch, capsys, fmt, command):
    def resolver(ss, backend, requested):
        value = ss.get("protein.query").value
        status = {
            "MISS": WeaveStatus.NO_MATCH,
            "FAIL": WeaveStatus.ERROR,
            "REVIEW": WeaveStatus.OK,
        }.get(value, WeaveStatus.OK)
        return WeaveResult(
            UP_CAP.id,
            "1.0.0",
            backend,
            frozenset({"g"}),
            status=status,
            strands=(Strand("protein.name", value),) if status is WeaveStatus.OK else (),
            requires_review=value == "REVIEW",
            errors=("503 source unavailable",) if value == "FAIL" else (),
        )

    registry = BraidRegistry()
    registry.register(ScriptedWeaver(resolver, capability=UP_CAP, weaver_id="uniprot"))
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: registry)
    path = tmp_path / "rows.txt"
    path.write_text("OK\nMISS\nREVIEW\nFAIL\nOK\n")
    prefix = ["run", "uniprot", UP_CAP.id] if command == "run" else ["weave"]
    assert (
        _run(
            *prefix,
            "--in-file",
            str(path),
            "--in-type",
            "protein.query",
            "--want",
            "protein.name",
            "--format",
            fmt,
        )
        == 1
    )
    output = capsys.readouterr().out
    rows = (
        json.loads(output)
        if fmt == "json"
        else list(csv.DictReader(io.StringIO(output), delimiter="\t" if fmt == "tsv" else ","))
    )
    assert [row["status"] for row in rows] == [
        "resolved",
        "unresolved",
        "review",
        "error",
        "resolved",
    ]
    assert [int(row["source_row"]) for row in rows] == [1, 2, 3, 4, 5]
    assert len({row["outcome"] for row in rows}) == 5
    assert "503" in str(rows[3]["diagnostics"])
    assert all("completion" in row and "missing" in row for row in rows)


def test_duplicate_inputs_retain_unique_source_rows_through_traversal(tmp_path, capsys):
    path = tmp_path / "duplicates.txt"
    path.write_text("P1\nP1\n")
    assert (
        _run(
            "weave",
            "--in-file",
            str(path),
            "--in-type",
            "protein.query",
            "--for-each",
            "structures",
            "--format",
            "json",
        )
        == 0
    )
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 4
    assert [row["source_row"] for row in rows] == [1, 1, 2, 2]
    assert len({row["outcome"] for row in rows}) == 4
    assert all(row["references"][0]["weaver_id"] == "pdbe" for row in rows)


def test_export_partial_branch_errors_do_not_duplicate_terminal_rows():
    from braidworks.core.executor import ExecutionError, ExecutionResult
    from braidworks.core.strand import StrandSet

    ss = StrandSet.from_strands(
        "duplicate", [Strand("protein.name", "name", confidence=0.8, provenance=("fixture:local",))]
    )
    ss.source_row = 1
    ss.warnings.append("partial data")
    result = ExecutionResult(resolved=[ss], errors=[ExecutionError(ss, "WeaverError", "503")])
    rows = cli._result_records(result, ["protein.name", "protein.length"])
    assert len(rows) == 1
    assert rows[0]["status"] == "resolved"
    assert rows[0]["missing"] == ["protein.length"]
    assert rows[0]["warnings"] == ["partial data"]
    assert rows[0]["diagnostics"][0]["message"] == "503"
    assert rows[0]["strands"]["protein.name"]["confidence"] == 0.8
    assert rows[0]["strands"]["protein.name"]["provenance"] == ["fixture:local"]


def test_multiple_fatal_diagnostics_produce_one_error_row():
    from braidworks.core.executor import ExecutionError, ExecutionResult
    from braidworks.core.strand import StrandSet

    ss = StrandSet("same")
    result = ExecutionResult(
        errors=[ExecutionError(ss, "WeaverError", message) for message in ("503", "timeout")]
    )
    rows = cli._result_records(result, ["protein.name"])
    assert len(rows) == 1
    assert rows[0]["status"] == "error"
    assert len(rows[0]["diagnostics"]) == 2


@pytest.mark.parametrize("fmt", ["json", "tsv"])
def test_cli_exports_and_reports_expansion_truncation(tmp_path, capsys, fmt):
    path = tmp_path / "duplicates.txt"
    path.write_text("P1\nP1\n")
    assert (
        _run(
            "weave",
            "--in-file",
            str(path),
            "--in-type",
            "protein.query",
            "--for-each",
            "structures",
            "--max-expansion",
            "3",
            "--format",
            fmt,
        )
        == 0
    )
    captured = capsys.readouterr()
    rows = (
        json.loads(captured.out)
        if fmt == "json"
        else list(csv.DictReader(io.StringIO(captured.out), delimiter="\t"))
    )
    assert len(rows) == 3
    assert [int(row["source_row"]) for row in rows] == [1, 1, 2]
    truncations = rows[-1]["truncations"]
    if fmt == "tsv":
        truncations = json.loads(truncations)
    assert truncations[0]["omitted"] == 1
    assert "expansion limit 3" in captured.err


def test_sparse_route_groups_share_expansion_budget(tmp_path, capsys):
    path = tmp_path / "sparse.tsv"
    path.write_text("protein.query\tprotein.uniprot.accession\nP1\t\n\tACC_P2\n")
    assert (
        _run(
            "weave",
            "--in-file",
            str(path),
            "--want",
            "pdb.id",
            "--expand",
            "all",
            "--max-expansion",
            "3",
            "--format",
            "json",
        )
        == 0
    )
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 3
    assert [row["source_row"] for row in rows] == [1, 1, 2]
    assert rows[-1]["truncations"][0]["kept"] == 1


def test_weave_batch_one_per_line(tmp_path, capsys):
    f = tmp_path / "ids.txt"
    f.write_text("P1\n# comment\n\nP2\n")
    _run(
        "weave",
        "--in-file",
        str(f),
        "--in-type",
        "protein.query",
        "--want",
        "protein.name",
        "--format",
        "jsonl",
    )
    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert [r["entity"] for r in lines] == ["P1", "P2"]  # entity id = the value


def test_weave_batch_tsv_table(tmp_path, capsys):
    f = tmp_path / "in.tsv"
    f.write_text("protein.query\nP1\nP2\n")
    _run("weave", "--in-file", str(f), "--want", "protein.name", "--format", "tsv")
    rows = capsys.readouterr().out.strip().splitlines()
    assert len(rows) == 3  # header + 2


@pytest.mark.parametrize("traverse", [False, True])
def test_table_stdin_is_read_once(monkeypatch, capsys, traverse):
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("protein.query\nP1\nP2\n"))
    extra = ["--for-each", "structures"] if traverse else ["--want", "protein.name"]
    assert _run("weave", "--in-file", "-", "--format", "json", *extra) == 0
    records = json.loads(capsys.readouterr().out)
    assert len(records) == (4 if traverse else 2)
    assert {r.get("parent", r["entity"]) for r in records} == {"e1", "e2"}


def test_table_columns_are_available_with_broadcast_constants(tmp_path, capsys):
    f = tmp_path / "in.tsv"
    f.write_text("protein.query\nP1\nP2\n")
    assert (
        _run(
            "weave",
            "--in-file",
            str(f),
            "--have",
            "ncbi.taxon.id=9606",
            "--want",
            "protein.name",
            "--format",
            "json",
        )
        == 0
    )
    records = json.loads(capsys.readouterr().out)
    assert [r["values"]["protein.name"] for r in records] == ["Name of P1", "Name of P2"]


@pytest.mark.parametrize("traverse", [False, True])
def test_sparse_table_plans_from_each_rows_actual_inputs(tmp_path, capsys, traverse):
    f = tmp_path / "mixed.tsv"
    f.write_text("protein.query\tprotein.uniprot.accession\nP1\t\n\tACC_P2\n")
    extra = ["--for-each", "structures"] if traverse else ["--want", "structure.pdb.ids"]
    assert _run("weave", "--in-file", str(f), "--format", "json", *extra) == 0
    records = json.loads(capsys.readouterr().out)
    assert len(records) == (4 if traverse else 2)
    assert {r.get("parent", r["entity"]) for r in records} == {"e1", "e2"}


@pytest.mark.parametrize("command", ["run", "weave"])
def test_parameter_scope_must_name_an_executed_capability(capsys, command):
    direct = ["pdbe", "list_structures"] if command == "run" else []
    assert (
        _run(
            command,
            *direct,
            "--have",
            "protein.uniprot.accession=ACC_X",
            "--want",
            "structure.pdb.ids",
            "--param",
            "wrong:level=best",
        )
        == 1
    )
    assert "wrong" in capsys.readouterr().err


@pytest.mark.parametrize("parameter", ["organism=9606", "resolve_protein:organism=9606"])
def test_traversal_parameters_reach_resolver_prelude(monkeypatch, capsys, parameter):
    from dataclasses import replace

    reg = _make_registry()
    resolver = reg.get_weaver("uniprot")
    resolver._manifest = replace(
        resolver.MANIFEST,
        capabilities=(replace(UP_CAP, parameters=(Parameter("organism", type="int"),)),),
    )
    updated = BraidRegistry()
    updated.register(resolver)
    updated.register(reg.get_weaver("pdbe"))
    reg = updated
    seen = []
    original = resolver.execute_batch

    async def recording(*args, params=None, **kwargs):
        seen.append(params)
        return await original(*args, params=params, **kwargs)

    monkeypatch.setattr(resolver, "execute_batch", recording)
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: reg)
    assert (
        _run(
            "weave",
            "--have",
            "protein.query=TP53",
            "--for-each",
            "structures",
            "--param",
            parameter,
            "--format",
            "json",
        )
        == 0
    )
    assert seen == [{"organism": 9606}]
    assert len(json.loads(capsys.readouterr().out)) == 2


def test_all_parameter_values_are_validated_before_upstream_io(monkeypatch, capsys):
    registry = _make_registry()
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: registry)
    assert (
        _run(
            "weave",
            "--have",
            "protein.query=P1",
            "--want",
            "structure.pdb.ids",
            "--param",
            "list_structures:level=nope",
        )
        == 1
    )
    assert "not in allowed values" in capsys.readouterr().err
    assert registry.get_weaver("uniprot").batch_calls == 0
    assert registry.get_weaver("pdbe").batch_calls == 0


def test_sparse_rows_still_batch_matching_input_types(tmp_path, monkeypatch, capsys):
    registry = _make_registry()
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: registry)
    path = tmp_path / "mixed.tsv"
    path.write_text("protein.query\tprotein.uniprot.accession\nP1\t\n\tACC_P2\nP3\t\n")
    assert (
        _run("weave", "--in-file", str(path), "--want", "structure.pdb.ids", "--format", "json")
        == 0
    )
    assert len(json.loads(capsys.readouterr().out)) == 3
    assert registry.get_weaver("uniprot").batch_sizes == [2]
    assert registry.get_weaver("pdbe").batch_sizes == [2, 1]


def test_csv_table_stdin_detects_header_delimiter(monkeypatch, capsys):
    monkeypatch.setattr(
        cli.sys, "stdin", io.StringIO("protein.query,ncbi.taxon.id\nP1,9606\nP2,9606\n")
    )
    assert _run("weave", "--in-file", "-", "--want", "protein.name", "--format", "json") == 0
    assert len(json.loads(capsys.readouterr().out)) == 2


@pytest.mark.parametrize("delimiter", [",", "\t"])
@pytest.mark.parametrize("traverse", [False, True])
def test_cli_subprocess_reads_nonseekable_table_stdin(delimiter, traverse):
    script = (
        "from braidworks.core import cli; "
        "from tests.test_cli import _make_registry; "
        "cli.build_registry_from_entry_points = _make_registry; "
        "raise SystemExit(cli.main())"
    )
    extra = ["--for-each", "structures"] if traverse else ["--want", "protein.name"]
    completed = subprocess.run(
        [sys.executable, "-c", script, "weave", "--in-file", "-", "--format", "json", *extra],
        input=f"protein.query{delimiter}ncbi.taxon.id\nP1{delimiter}9606\nP2{delimiter}9606\n",
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    assert len(json.loads(completed.stdout)) == (4 if traverse else 2)


def test_weave_fanout_expands_children(capsys):
    _run(
        "weave",
        "--have",
        "protein.query=P1",
        "--want",
        "structure.pdb.ids",
        "--expand",
        "all",
        "--format",
        "jsonl",
    )
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
    code = _run(
        "run", "uniprot", "resolve_protein", "--have", "protein.query=P1", "--want", "protein.name"
    )
    assert code == 0
    assert "Name of P1" in capsys.readouterr().out


def test_run_infers_sole_backend(capsys):
    code = _run("run", "pdbe", "list_structures", "--have", "protein.uniprot.accession=ACC_X")
    assert code == 0
    assert "ACC_X-1" in capsys.readouterr().out


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize(
    "status,expected",
    [
        (WeaveStatus.ERROR, "error"),
        (WeaveStatus.NO_MATCH, "unresolved"),
        (WeaveStatus.AMBIGUOUS, "review"),
    ],
)
def test_run_preserves_failure_and_review_status(monkeypatch, capsys, status, expected, strict):
    from braidworks.core.result import CandidateResult

    reg = BraidRegistry()
    reg.register(
        ScriptedWeaver(
            lambda ss, b, r: WeaveResult(
                UP_CAP.id,
                "1.0.0",
                b,
                frozenset({"g"}),
                status=status,
                errors=("503 Service Unavailable",) if status is WeaveStatus.ERROR else (),
                candidates=(CandidateResult(strands=(Strand("protein.name", "candidate"),)),)
                if status is WeaveStatus.AMBIGUOUS
                else (),
            ),
            capability=UP_CAP,
            weaver_id="uniprot",
        )
    )
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: reg)
    args = ["--strict"] if strict else []
    code = _run(
        "run", "uniprot", UP_CAP.id, "--have", "protein.query=P1", "--format", "json", *args
    )
    captured = capsys.readouterr()
    assert code == int(strict or status is WeaveStatus.ERROR)
    record = json.loads(captured.out)[0]
    assert record["status"] == expected
    if status is WeaveStatus.ERROR:
        assert "503" in captured.err
        assert record["errors"] == ["503 Service Unavailable"]
    if status is WeaveStatus.AMBIGUOUS:
        assert record["candidates"][0]["strands"][0]["value"] == "candidate"


def test_run_rejects_undeclared_backend(capsys):
    assert (
        _run("run", "uniprot", UP_CAP.id, "--have", "protein.query=P1", "--backend", "bogus") == 1
    )
    assert "backend" in capsys.readouterr().err


def test_run_reports_configuration_exception_without_traceback(monkeypatch, capsys):
    from braidworks.core.exceptions import BackendConfigurationError

    def broken(ss, b, r):
        raise BackendConfigurationError("test database unavailable")

    reg = BraidRegistry()
    reg.register(ScriptedWeaver(broken, capability=UP_CAP, weaver_id="uniprot"))
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: reg)
    assert _run("run", "uniprot", UP_CAP.id, "--have", "protein.query=P1") == 1
    assert "test database unavailable" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["run", "weave"])
@pytest.mark.parametrize("count", [0, 2])
def test_cli_reports_malformed_batch_without_partial_output(monkeypatch, capsys, command, count):
    class MalformedWeaver(ScriptedWeaver):
        async def execute_batch(self, cid, inputs, *, requested_outputs, backend, params=None):
            return [
                WeaveResult(cid, "1.0.0", backend, frozenset(), status=WeaveStatus.NO_MATCH)
                for _ in range(count)
            ]

    registry = BraidRegistry()
    registry.register(MalformedWeaver(lambda *_: None, capability=UP_CAP, weaver_id="uniprot"))
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: registry)
    prefix = ["run", "uniprot", UP_CAP.id] if command == "run" else ["weave"]
    code = _run(*prefix, "--have", "protein.query=P1", "--want", "protein.name", "--format", "json")
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert f"returned {count} results for 1 inputs" in captured.err


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
    code = _run(
        "weave", "--have", "protein.query=P1", "--want", "structure.pdb.ids", "--only", "uniprot"
    )
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
    code = _run(
        "weave",
        "--have",
        "protein.query=P1",
        "--want",
        "structure.pdb.ids",
        "--param",
        "level=best",
    )
    assert code == 0
    assert "ACC_P1-1" in capsys.readouterr().out


def test_weave_rejects_param_outside_enum(capsys):
    code = _run(
        "weave",
        "--have",
        "protein.query=P1",
        "--want",
        "structure.pdb.ids",
        "--param",
        "level=nope",
    )
    assert code == 1
    assert "not in allowed values" in capsys.readouterr().err


def test_weave_rejects_unknown_param_name(capsys):
    code = _run(
        "weave", "--have", "protein.query=P1", "--want", "structure.pdb.ids", "--param", "bogus=1"
    )
    assert code == 1
    assert "no step in this route accepts" in capsys.readouterr().err


def test_run_accepts_param(capsys):
    code = _run(
        "run",
        "pdbe",
        "list_structures",
        "--have",
        "protein.uniprot.accession=ACC_X",
        "--param",
        "level=best",
    )
    assert code == 0


# --- traversal fan-out (--for-each / --traverse) -----------------------------------


def test_for_each_fans_through_relationship(capsys):
    # 'structures' = list_structures (a fan capability) minus the list_ prefix.
    code = _run(
        "weave",
        "--have",
        "protein.uniprot.accession=ACC_X",
        "--for-each",
        "structures",
        "--format",
        "json",
    )
    out = capsys.readouterr()
    assert code == 0
    records = json.loads(out.out)
    # one child per fanned pdb.id, each re-rooted (parent = original entity), all regroup
    assert len(records) == 2
    assert {r["parent"] for r in records} == {"e1"}
    assert sorted(r["values"]["pdb.id"] for r in records) == ["ACC_X-1", "ACC_X-2"]


def test_traverse_accepts_capability_id(capsys):
    code = _run(
        "weave",
        "--have",
        "protein.uniprot.accession=ACC_X",
        "--traverse",
        "list_structures",
        "--format",
        "json",
    )
    assert code == 0
    assert len(json.loads(capsys.readouterr().out)) == 2


def test_for_each_unknown_relationship_errors(capsys):
    code = _run("weave", "--have", "protein.uniprot.accession=ACC_X", "--for-each", "bogus")
    assert code == 1
    assert "no traversal" in capsys.readouterr().err


@pytest.mark.parametrize("partial_success", [False, True])
def test_traversal_exit_status_depends_on_blocking_errors(monkeypatch, capsys, partial_success):
    from tests.helpers import simple_capability

    reg = _make_registry()
    for cap_id, target in (
        ("describe_title", "structure.pdb.title"),
        ("describe_method", "structure.pdb.method"),
    ):

        def describe(ss, backend, requested, cid=cap_id, output=target):
            if partial_success and output == "structure.pdb.title":
                return WeaveResult(
                    cid,
                    "1.0.0",
                    backend,
                    frozenset({"g"}),
                    status=WeaveStatus.OK,
                    strands=(Strand(output, "title"),),
                )
            return WeaveResult(
                cid,
                "1.0.0",
                backend,
                frozenset({"g"}),
                status=WeaveStatus.ERROR,
                errors=("503 Service Unavailable",),
            )

        reg.register(
            ScriptedWeaver(
                describe,
                capability=simple_capability(cap_id, {"pdb.id"}, {target}),
                weaver_id=cap_id,
            )
        )
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: reg)
    code = _run(
        "weave",
        "--have",
        "protein.uniprot.accession=ACC_X",
        "--for-each",
        "structures",
        "--want",
        "structure.pdb.title,structure.pdb.method",
        "--format",
        "json",
    )
    captured = capsys.readouterr()
    assert code == int(not partial_success)
    assert "503" in captured.err
    if partial_success:
        assert len(json.loads(captured.out)) == 2


# --- structural errors are reported, not silent -------------------------------------


def test_weave_reports_structural_error_and_exits_nonzero(monkeypatch, capsys):
    """A node that 5xx's must not vanish into an empty result with exit 0."""
    boom_cap = Capability(
        id="boom",
        consumes=frozenset({"protein.query"}),
        produces=frozenset({"protein.name"}),
        output_groups=(OutputGroup(id="g", outputs=frozenset({"protein.name"})),),
        backends=("api",),
    )

    def boom(ss, b, r):
        return WeaveResult(
            "boom",
            "1.0.0",
            b,
            frozenset({"g"}),
            status=WeaveStatus.ERROR,
            errors=("Server error '503'",),
        )

    reg = BraidRegistry()
    reg.register(ScriptedWeaver(boom, capability=boom_cap, weaver_id="boomw"))
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: reg)

    code = _run("weave", "--have", "protein.query=X", "--want", "protein.name")
    err = capsys.readouterr().err
    assert code == 1  # fatal structural error → non-zero (was: silent exit 0)
    assert "error(s)" in err
    assert "unavailable" in err  # the plain-English category explanation


def test_run_rejects_bad_param(capsys):
    code = _run(
        "run",
        "pdbe",
        "list_structures",
        "--have",
        "protein.uniprot.accession=ACC_X",
        "--param",
        "level=nope",
    )
    assert code == 1
    assert "not in allowed values" in capsys.readouterr().err


def test_parse_params_forms():
    assert cli._parse_params(["a=1", "cap:b=2"]) == [(None, "a", "1"), ("cap", "b", "2")]
    with pytest.raises(SystemExit):
        cli._parse_params(["noequals"])


@pytest.mark.parametrize("command", ["weave", "run", "traverse"])
def test_run_archive_preserves_inputs_defaults_and_outcomes(tmp_path, capsys, command):
    archive = tmp_path / "run.json"
    shared = [
        "--have",
        "protein.query=P1",
        "--want",
        "structure.pdb.ids",
        "--archive",
        str(archive),
        "--format",
        "json",
    ]
    if command == "run":
        argv = [
            "run",
            "pdbe",
            "list_structures",
            "--have",
            "protein.uniprot.accession=ACC_P1",
            "--want",
            "structure.pdb.ids",
            "--archive",
            str(archive),
            "--format",
            "json",
        ]
    elif command == "traverse":
        argv = ["weave", "--traverse", "list_structures", *shared]
    else:
        argv = ["weave", *shared]
    assert _run(*argv) == 0
    data = json.loads(archive.read_text())
    printed = json.loads(capsys.readouterr().out)
    assert data["schema"] == "braidworks.run-archive.v1"
    assert data["records"] == printed
    assert data["effective_params"]["list_structures"] == {"level": "all"}
    assert data["planned_routes"]
    assert data["sources"][0]["backend_fingerprints"]["api"]["value"]
    assert "structure.pdb.ids" not in data["inputs"][0]["strands"]
    assert data["finished_at"] >= data["started_at"]
    assert archive.stat().st_mode & 0o777 == 0o600
    if command != "run":
        from braidworks.core.executor import ExecutionResult

        assert ExecutionResult.from_json(data["execution"]).resolved


def test_archive_records_unresolved_inputs_without_losing_them(tmp_path, capsys):
    archive = tmp_path / "miss.json"
    assert (
        _run(
            "weave",
            "--have",
            "protein.query=MISS",
            "--want",
            "protein.name",
            "--strict",
            "--archive",
            str(archive),
        )
        == 1
    )
    data = json.loads(archive.read_text())
    assert data["records"][0]["status"] == "unresolved"
    assert data["execution"]["unresolved"]


def test_archive_refuses_overwrite_and_cleans_temporary_files(tmp_path, capsys):
    archive = tmp_path / "existing.json"
    archive.write_text("keep me")
    assert (
        _run(
            "weave",
            "--have",
            "protein.query=P1",
            "--want",
            "protein.name",
            "--archive",
            str(archive),
        )
        == 1
    )
    assert archive.read_text() == "keep me"
    assert "could not write run archive" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == [archive]
