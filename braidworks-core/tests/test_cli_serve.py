"""`braidworks serve` starts the browser interface that weaverkit provides."""

import sys

import pytest
from braidworks.core import cli


def test_serve_without_weaverkit_explains_the_install(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "weaverkit.cli", None)  # import fails
    assert cli.main(["serve", "--no-open"]) == 1
    err = capsys.readouterr().err
    assert "braidworks serve needs the browser interface" in err
    assert "weaverkit[serve]" in err


def test_serve_passes_its_options_to_weaverkit(monkeypatch):
    weaverkit_cli = pytest.importorskip("weaverkit.cli")
    seen = {}

    def fake_serve(**kwargs):
        seen.update(kwargs)

    monkeypatch.setattr("weaverkit.serve.serve", fake_serve)
    argv = ["serve", "--port", "8800", "--host", "0.0.0.0", "--data-dir", "d", "--no-open"]
    assert cli.main(argv) == 0
    assert seen == {"host": "0.0.0.0", "port": 8800, "open_browser": False, "data_dir": "d"}
    assert weaverkit_cli.cmd_serve  # the same command `weaverkit serve` runs


def test_busy_port_exits_1_with_the_message(monkeypatch, capsys):
    pytest.importorskip("weaverkit.cli")
    from weaverkit.serve import PortInUseError

    def busy(**kwargs):
        raise PortInUseError("port 8765 is already in use on 127.0.0.1 … --port 8766.")

    monkeypatch.setattr("weaverkit.serve.serve", busy)
    assert cli.main(["serve", "--no-open"]) == 1
    captured = capsys.readouterr()
    assert "--port 8766" in captured.err
    assert "http://" not in captured.out + captured.err
