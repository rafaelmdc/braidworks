"""Run Celery in eager mode so the suite needs no Redis broker or worker.

In eager mode ``apply_async`` executes the task inline and ``.get()`` returns its
stored result — exercising the real task body, serialization, runner, and executor
wiring without a broker. The per-process registry is reset around every test.
"""

from __future__ import annotations

import pytest

from braidworks_celery import discovery
from braidworks_celery.app import app


@pytest.fixture(autouse=True)
def _eager():
    prev = app.conf.task_always_eager
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True
    yield
    app.conf.task_always_eager = prev


@pytest.fixture(autouse=True)
def _clean_registry():
    discovery.set_registry(None)
    yield
    discovery.set_registry(None)
