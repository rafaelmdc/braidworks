"""Builders for idmapping_weaver — how the weaver is assembled from its backends."""

from __future__ import annotations

from typing import Any

from braidworks.core import BaseWeaver

from idmapping_weaver.backends.api import IdMappingApiBackend
from idmapping_weaver.weaver import IdmappingWeaver


def build_idmapping_weaver(**_config: Any) -> BaseWeaver:
    """Zero-config introspection builder (``weaverkit verify``'s entry point).

    The UniProt ID-mapping service is keyless, so the api backend is always usable.
    """
    return IdmappingWeaver({"api": IdMappingApiBackend()})


def build_idmapping_weaver_fixture() -> BaseWeaver:
    """Fixture-backed weaver for ``verify --strict`` — canned API, no network.

    The keyless api backend is always configured, so without this golden would hit the
    live service. Wires the api backend to an ``httpx.MockTransport`` (see ``fixture.py``).
    """
    from idmapping_weaver.fixture import mock_client

    return IdmappingWeaver({"api": IdMappingApiBackend(client=mock_client())})
