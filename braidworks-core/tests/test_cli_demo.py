"""`braidworks demo` and `bw.demo()` delegate to weaverkit's offline demo."""

import sys
import types
from dataclasses import dataclass

import braidworks as bw
import pytest
from braidworks.core import cli


@dataclass(frozen=True)
class FakeDemo:
    name: str
    title: str = "A title"
    point: str = "A point."

    def example(self):
        return {"name": self.title}


class FakeResult:
    def __init__(self):
        self.rows = [{"input": "x", "row": 1, "status": "resolved", "f": "v", "missing": []}]
        self.want = ["f"]

    def to_json(self):
        return {"rows": self.rows}

    def summary(self):
        return "1 input · 1 resolved · 0 unresolved · 0 need review · 0 errors"


@pytest.fixture
def fake_weaverkit(monkeypatch):
    demos = (FakeDemo("first"), FakeDemo("second"))
    calls = {}
    module = types.ModuleType("weaverkit.demo")
    module.NOTICE = "Demo mode: sample data."
    module.DEMOS = demos

    def find_demo(name):
        for item in demos:
            if item.name == name:
                return item
        raise ValueError(f"no demo named {name!r}; choose one of: first, second")

    def run(name=None):
        calls["run"] = name
        return [(item, FakeResult()) for item in demos if name in (None, item.name)]

    module.find_demo = find_demo
    module.run = run
    module.demo_registry = lambda: "registry"
    module.runnable = lambda registry: list(demos)
    package = types.ModuleType("weaverkit")
    package.demo = module
    monkeypatch.setitem(sys.modules, "weaverkit", package)
    monkeypatch.setitem(sys.modules, "weaverkit.demo", module)
    return calls


def test_demo_without_weaverkit_explains_the_install(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "weaverkit", None)
    assert cli.main(["demo"]) == 1
    assert "pip install braidworks" in capsys.readouterr().err


def test_demo_runs_every_query_and_labels_the_sample_data(fake_weaverkit, capsys):
    assert cli.main(["demo"]) == 0
    out, err = capsys.readouterr()
    assert fake_weaverkit["run"] is None
    assert "braidworks demo first" in out and "braidworks demo second" in out
    assert "x  [resolved]" in out
    assert err.startswith("Demo mode: sample data.")


def test_one_demo_as_csv(fake_weaverkit, capsys):
    assert cli.main(["demo", "second", "--format", "csv"]) == 0
    out = capsys.readouterr().out
    assert fake_weaverkit["run"] == "second"
    assert out.splitlines() == ["input,row,status,f,missing", "x,1,resolved,v,"]


def test_machine_formats_need_one_demo(fake_weaverkit, capsys):
    assert cli.main(["demo", "--format", "json"]) == 1
    assert "name a demo" in capsys.readouterr().err
    assert "run" not in fake_weaverkit


def test_unknown_demo_is_refused(fake_weaverkit, capsys):
    assert cli.main(["demo", "nope"]) == 1
    assert "choose one of: first, second" in capsys.readouterr().err


def test_list_names_each_demo(fake_weaverkit, capsys):
    assert cli.main(["demo", "--list"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("first") and "A point." in out


def test_serve_opens_the_browser_on_the_demo_sources(fake_weaverkit, monkeypatch):
    seen = {}
    serve_module = types.ModuleType("weaverkit.serve")
    serve_module.serve = lambda **kwargs: seen.update(kwargs)
    monkeypatch.setitem(sys.modules, "weaverkit.serve", serve_module)
    assert cli.main(["demo", "--serve", "--no-open", "--port", "8800"]) == 0
    assert seen == {
        "port": 8800,
        "open_browser": False,
        "registry": "registry",
        "examples": [{"name": "A title"}, {"name": "A title"}],
        "notice": "Demo mode: sample data.",
    }


def test_python_demo_returns_the_result(fake_weaverkit):
    result = bw.demo("first")
    assert isinstance(result, FakeResult)
    assert fake_weaverkit["run"] == "first"


def test_python_demo_without_weaverkit(monkeypatch):
    monkeypatch.setitem(sys.modules, "weaverkit", None)
    with pytest.raises(ImportError, match="pip install braidworks"):
        bw.demo()
