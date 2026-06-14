"""Builders for bacdive_weaver — how the weaver is assembled from its backends.

Two-builder convention (see weaverkit/docs/decisions.md C/D):

- ``build_bacdive_weaver()`` — the ZERO-CONFIG *introspection* builder that
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

from bacdive_weaver.backends.api import BacdiveApiBackend
from bacdive_weaver.weaver import BacdiveWeaver


def build_bacdive_weaver(**_config: Any) -> BaseWeaver:
    """Zero-config introspection builder (``weaverkit verify``'s entry point).

    The BacDive v2 API needs no key, so the api backend is usable as-is and this is
    also the real production builder. Pass ``client=`` / ``max_strains_scanned=`` to
    tune it (see ``build_bacdive_weaver_configured``).
    """
    return BacdiveWeaver({"api": BacdiveApiBackend()})


def build_bacdive_weaver_configured(
    *, client: httpx.AsyncClient | None = None, max_strains_scanned: int = 200, **_config: Any
) -> BaseWeaver:
    """Configured builder: inject an HTTP client and/or cap the type-strain scan."""
    return BacdiveWeaver(
        {"api": BacdiveApiBackend(client=client, max_strains_scanned=max_strains_scanned)}
    )


def build_bacdive_weaver_fixture() -> BaseWeaver:
    """Fixture-backed weaver for ``verify --strict`` — canned responses, no network.

    The api backend is always configured (the v2 API is keyless), so without this
    fixture golden would hit the live service. Wires the backend to an
    ``httpx.MockTransport`` serving a tiny *Escherichia coli* dataset whose type
    strain has the asserted traits (see ``bacdive_weaver.fixture``).
    """
    from bacdive_weaver.fixture import mock_client

    return BacdiveWeaver({"api": BacdiveApiBackend(client=mock_client())})
