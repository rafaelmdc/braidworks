"""Reset the per-process registry around every test; the suite uses no Redis."""

from __future__ import annotations

import pytest

from braidworks_arq import discovery


@pytest.fixture(autouse=True)
def _clean_registry():
    discovery.set_registry(None)
    yield
    discovery.set_registry(None)
