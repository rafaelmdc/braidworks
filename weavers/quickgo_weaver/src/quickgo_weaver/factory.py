"""Builders for quickgo_weaver — how the weaver is assembled from its backends.

Two-builder convention (see weaverkit/docs/decisions.md C/D):

- ``build_quickgo_weaver()`` — the ZERO-CONFIG *introspection* builder that
  ``weaverkit verify`` calls. It wires every declared backend present (possibly
  unconfigured), so the manifest is complete and fingerprint/golden checks can run.
  It never raises for missing data.
- a CONFIGURED builder (you write it, usually domain-named) — takes real config
  (db paths, API keys, injected clients) and may raise if nothing is usable. See
  ``ncbi_weaver``'s ``build_ncbi_weaver`` for a worked example; a commented
  skeleton is at the bottom of this file.
"""

from __future__ import annotations

from typing import Any

import httpx
from braidworks.core import BaseWeaver

from quickgo_weaver.backends.api import DEFAULT_BASE_URL, QuickgoApiBackend
from quickgo_weaver.weaver import QuickgoWeaver


def build_quickgo_weaver(
    *,
    base_url: str = DEFAULT_BASE_URL,
    client: httpx.AsyncClient | None = None,
    max_pages: int = 10,
    **_config: Any,
) -> BaseWeaver:
    """Zero-config introspection builder (``weaverkit verify``'s entry point).

    With no arguments, wires the keyless API for introspection. Explicit endpoint,
    client and source-policy arguments configure the same backend for real queries.
    """
    backends = {
        "api": QuickgoApiBackend(base_url=base_url, client=client, max_pages=max_pages),
    }
    return QuickgoWeaver(backends)


def build_quickgo_weaver_fixture() -> BaseWeaver:
    """Fixture-backed weaver for ``verify --strict`` — canned API, no network.

    The keyless api backend is always configured, so without this golden would
    hit the live service. Wires the api backend to an ``httpx.MockTransport``
    (see ``fixture.py`` — fill in its canned responses).
    """
    from quickgo_weaver.fixture import mock_client

    return QuickgoWeaver({"api": QuickgoApiBackend(client=mock_client())})


# --- Optional builders (uncomment + fill in for real use) -----------------------
#
# A CONFIGURED builder — takes real config and raises if nothing is usable:
#
# from braidworks.core import BackendConfigurationError
#
# def build_quickgo_weaver_configured(**config: Any) -> BaseWeaver:
#     backends = {}
#     # ... wire backends from real config (paths / keys / clients) ...
#     if not backends:
#         raise BackendConfigurationError("configure at least one backend")
#     return QuickgoWeaver(backends)
