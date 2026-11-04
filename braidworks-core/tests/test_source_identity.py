import sqlite3

import pytest
from braidworks.core.exceptions import BackendConfigurationError
from braidworks.core.source_identity import SourceBinding, SourceIdentity


def _database(path):
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE meta (key, value)")
        connection.execute("INSERT INTO meta VALUES ('release', 'same')")


def test_generation_and_roundtrip(tmp_path):
    path = tmp_path / "db"
    _database(path)
    binding = SourceBinding(path, lambda con: dict(con.execute("SELECT * FROM meta")))
    first = binding.fingerprint()
    assert binding.fingerprint() == first
    assert SourceIdentity.from_json(binding._expected.to_json()) == binding._expected
    replacement = tmp_path / "replacement"
    _database(replacement)
    replacement.replace(path)
    with pytest.raises(BackendConfigurationError, match="reopen"):
        binding.fingerprint()
    assert SourceBinding(path, binding._metadata).fingerprint() != first


def test_component_changes_reject(tmp_path):
    path = tmp_path / "db"
    _database(path)
    component = tmp_path / "tree"
    component.write_text("first")
    binding = SourceBinding(path, lambda con: {}, components=(component,))
    binding.fingerprint()
    component.write_text("second generation")
    with pytest.raises(BackendConfigurationError, match="reopen"), binding.session():
        pass


def test_existing_session_rejects_mid_read_replacement(tmp_path):
    path = tmp_path / "db"
    _database(path)
    binding = SourceBinding(path, lambda con: {})
    with (
        pytest.raises(BackendConfigurationError, match="during lookup"),
        binding.session() as connection,
    ):
        replacement = tmp_path / "replacement"
        _database(replacement)
        replacement.replace(path)
        assert connection.execute("SELECT value FROM meta").fetchone()[0] == "same"
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
