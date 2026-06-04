"""build_ncbi_weaver — configuration-driven assembly of NCBITaxonWeaver.

Configures the ``local`` and ``api`` backends independently. A backend that is
not configured is simply not registered (it never poisons the weaver); the braider
can still plan against the remaining backend, and an unconfigured backend only
surfaces as ``BackendUnavailable`` if a step actually selects it with no fallback.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from braidworks.core import BackendConfigurationError

from .backends.datasets_v2 import DEFAULT_BASE_URL, DatasetsV2Backend
from .backends.local import LocalTaxonomyBackend
from .weaver import NCBITaxonWeaver


def build_ncbi_weaver(
    *,
    db_path: str | Path | None = None,
    cache_db_path: str | Path | None = None,
    enable_api: bool = False,
    api_base_url: str = DEFAULT_BASE_URL,
    api_key: str | None = None,
    api_client: httpx.AsyncClient | None = None,
    allow_fuzzy: bool = True,
) -> NCBITaxonWeaver:
    backends = {}
    if db_path is not None:
        backends["local"] = LocalTaxonomyBackend(db_path, cache_db_path=cache_db_path)
    if enable_api or api_client is not None:
        backends["api"] = DatasetsV2Backend(
            base_url=api_base_url,
            api_key=api_key,
            client=api_client,
            allow_fuzzy=allow_fuzzy,
        )
    if not backends:
        raise BackendConfigurationError(
            "build_ncbi_weaver: configure at least one backend "
            "(pass db_path for local and/or enable_api for the API backend)"
        )
    return NCBITaxonWeaver(backends)
