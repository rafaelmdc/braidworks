"""`serve` binds its port before announcing a URL; a busy port fails clearly."""

from __future__ import annotations

import socket

import pytest

from weaverkit import serve as serve_module


@pytest.fixture
def busy_port():
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    yield holder.getsockname()[1]
    holder.close()


def test_bind_reports_a_busy_port_and_suggests_another(busy_port):
    with pytest.raises(serve_module.PortInUseError) as exc:
        serve_module.bind_port("127.0.0.1", busy_port)
    message = str(exc.value)
    assert f"port {busy_port} is already in use" in message
    assert "--port" in message
    assert isinstance(exc.value, RuntimeError)  # the CLIs report RuntimeError cleanly


def test_bind_returns_a_listening_socket():
    sock = serve_module.bind_port("127.0.0.1", 0)
    try:
        port = sock.getsockname()[1]
        assert port > 0
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass  # already accepting connections before uvicorn takes over
    finally:
        sock.close()


def test_busy_port_never_prints_a_url_or_opens_a_browser(busy_port, monkeypatch, capsys):
    pytest.importorskip("uvicorn")
    opened = []
    monkeypatch.setattr("webbrowser.open", opened.append)
    with pytest.raises(serve_module.PortInUseError):
        serve_module.serve(port=busy_port, open_browser=True)
    captured = capsys.readouterr()
    assert "http://" not in captured.out + captured.err
    assert not opened


def test_serve_announces_the_bound_url_and_hands_uvicorn_the_socket(monkeypatch, capsys):
    uvicorn = pytest.importorskip("uvicorn")
    pytest.importorskip("fastapi")
    seen = {}

    def fake_run(self, sockets=None):
        seen["sockets"] = sockets
        seen["port"] = sockets[0].getsockname()[1]
        for sock in sockets:
            sock.close()

    monkeypatch.setattr(uvicorn.Server, "run", fake_run)
    serve_module.serve(port=0, open_browser=False)
    assert len(seen["sockets"]) == 1
    assert f"open http://127.0.0.1:{seen['port']}" in capsys.readouterr().out
