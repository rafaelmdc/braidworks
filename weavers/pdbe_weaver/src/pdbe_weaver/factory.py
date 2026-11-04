"""Builders for pdbe_weaver — how the weaver is assembled from its backends.

Two-builder convention (see weaverkit/docs/decisions.md C/D):

- ``build_pdbe_weaver()`` — the ZERO-CONFIG *introspection* builder that
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
from braidworks.core.lifecycle import reject_unknown_options

from pdbe_weaver.backends.api import PdbeApiBackend
from pdbe_weaver.weaver import PdbeWeaver


def build_pdbe_weaver(
    *,
    base_url: str = "https://www.ebi.ac.uk/pdbe/api",
    client: httpx.AsyncClient | None = None,
    limit: int = 25,
    **_config: Any,
) -> BaseWeaver:
    """Build with explicit source settings; injected clients remain caller-owned."""
    reject_unknown_options(_config)
    return PdbeWeaver({"api": PdbeApiBackend(base_url=base_url, client=client, limit=limit)})


def build_pdbe_weaver_fixture() -> BaseWeaver:
    """Fixture-backed weaver for ``verify --strict`` — canned API, no network.

    The keyless api backend is always configured, so without this golden would
    hit the live service. Wires the api backend to an ``httpx.MockTransport``
    (see ``fixture.py`` — fill in its canned responses).
    """
    from pdbe_weaver.fixture import mock_client

    return PdbeWeaver({"api": PdbeApiBackend(client=mock_client())})


# --- Optional builders (uncomment + fill in for real use) -----------------------
#
# A CONFIGURED builder — takes real config and raises if nothing is usable:
#
# from braidworks.core import BackendConfigurationError
#
# def build_pdbe_weaver_configured(**config: Any) -> BaseWeaver:
#     backends = {}
#     # ... wire backends from real config (paths / keys / clients) ...
#     if not backends:
#         raise BackendConfigurationError("configure at least one backend")
#     return PdbeWeaver(backends)
