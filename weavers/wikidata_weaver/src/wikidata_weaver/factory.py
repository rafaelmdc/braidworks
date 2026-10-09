"""Builders for wikidata_weaver — how the weaver is assembled from its backends.

Two-builder convention (see weaverkit/docs/decisions.md C/D):

- ``build_wikidata_weaver()`` — the ZERO-CONFIG *introspection* builder that
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

from wikidata_weaver.backends.api import WikidataApiBackend
from wikidata_weaver.weaver import WikidataWeaver


def build_wikidata_weaver(
    *,
    base_url: str = "https://query.wikidata.org",
    client: httpx.AsyncClient | None = None,
    **_config: Any,
) -> BaseWeaver:
    """Build with explicit source settings; injected clients remain caller-owned."""
    reject_unknown_options(_config)
    return WikidataWeaver({"api": WikidataApiBackend(base_url=base_url, client=client)})


def build_wikidata_weaver_fixture() -> BaseWeaver:
    """Fixture-backed weaver for ``verify --strict`` — canned API, no network.

    The keyless api backend is always configured, so without this golden would
    hit the live service. Wires the api backend to an ``httpx.MockTransport``
    (see ``fixture.py`` — fill in its canned responses).
    """
    from wikidata_weaver.fixture import mock_client

    return WikidataWeaver({"api": WikidataApiBackend(client=mock_client())})


# --- Optional builders (uncomment + fill in for real use) -----------------------
#
# A CONFIGURED builder — takes real config and raises if nothing is usable:
#
# from braidworks.core import BackendConfigurationError
#
# def build_wikidata_weaver_configured(**config: Any) -> BaseWeaver:
#     backends = {}
#     # ... wire backends from real config (paths / keys / clients) ...
#     if not backends:
#         raise BackendConfigurationError("configure at least one backend")
#     return WikidataWeaver(backends)
