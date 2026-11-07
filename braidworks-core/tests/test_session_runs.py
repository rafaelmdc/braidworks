"""The CLI and Python share one execution path: Session plans, runs and resumes."""

import json

from braidworks._session import Session
from braidworks.core import cli
from braidworks.core.persistence_options import QueryPersistence
from braidworks.core.run_store import SQLiteRunStore
from braidworks.core.strand import Strand, StrandSet
from test_query import _registry


def _sets():
    ss = StrandSet.from_strands("e1", [Strand("input.a", "value")])
    ss.source_row = 1
    return [ss]


def _prepare(session):
    return session._prepare_sets(
        _sets(),
        ["output.value"],
        [],
        expand=None,
        review="halt",
        min_confidence=0.0,
        max_expansion=10_000,
        parameter_items=(),
    )


def test_saved_run_matches_in_memory_run_and_resumes_without_refetching(tmp_path):
    registry = _registry()
    runs = str(tmp_path / "runs.sqlite")
    saved = []
    with Session(registry=registry) as session:
        prepared = _prepare(session)
        memory = session._runner().run(session._execute(prepared, ["output.value"]))
        durable = session._runner().run(
            session._execute(
                prepared,
                ["output.value"],
                persistence=QueryPersistence(run_db=runs, run_id="one"),
                on_saved=saved.append,
            )
        )
        assert durable.rows == memory.rows
        assert saved and saved[-1].run_id == "one" and saved[-1].status == "complete"
        assert [cp.run_id for cp in SQLiteRunStore(runs, create=False).list()] == ["one"]

        calls = registry.get_weaver("a").batch_calls
        checkpoint, resumed = session._runner().run(
            session._resume_run("one", QueryPersistence(run_db=runs))
        )
        assert checkpoint.status == "complete"
        assert resumed.want == ["output.value"]
        assert resumed.rows == memory.rows
        assert registry.get_weaver("a").batch_calls == calls


def test_cli_weave_json_is_the_sessions_export(monkeypatch, capsys):
    registry = _registry()
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: registry)
    argv = ["weave", "--have", "input.a=value", "--want", "output.value", "--format", "json"]
    assert cli.main(argv) == 0
    printed = json.loads(capsys.readouterr().out)
    with Session(registry=_registry()) as session:
        result = session._runner().run(session._execute(_prepare(session), ["output.value"]))
    assert printed == json.loads(json.dumps(result.to_json()))
