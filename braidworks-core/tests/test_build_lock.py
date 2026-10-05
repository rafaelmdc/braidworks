"""Real process ownership, with pipe handshakes rather than elapsed-age guesses."""

import multiprocessing
import os

import pytest
from braidworks.core.exceptions import BackendConfigurationError
from braidworks.core.localdb import BuildLock


def _owner(path, pipe):
    with BuildLock(path):
        pipe.send("acquired")
        pipe.recv()


def test_live_owner_age_timeout_and_death_recovery(tmp_path):
    path = tmp_path / "db"
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=_owner, args=(path, child))
    process.start()
    try:
        assert parent.poll(10)
        assert parent.recv() == "acquired"
        os.utime(path.with_name("db.lock"), (1, 1))
        with (
            pytest.raises(BackendConfigurationError, match="Timed out"),
            BuildLock(path, timeout=0),
        ):
            pass
        process.terminate()
        process.join(10)
        assert not process.is_alive()
        with BuildLock(path, timeout=1):
            pass
    finally:
        if process.is_alive():
            process.terminate()
        process.join(10)
        parent.close()
        child.close()


def test_release_does_not_release_other_owner(tmp_path):
    path = tmp_path / "db"
    old = BuildLock(path)
    with old, pytest.raises(RuntimeError, match="already acquired"):
        old.__enter__()
    with BuildLock(path):
        old.__exit__()
        with (
            pytest.raises(BackendConfigurationError, match="Timed out"),
            BuildLock(path, timeout=0),
        ):
            pass


@pytest.mark.parametrize("timeout", [-1, float("nan"), float("inf")])
def test_invalid_timeout(tmp_path, timeout):
    with pytest.raises(ValueError):
        BuildLock(tmp_path / "db", timeout=timeout)
