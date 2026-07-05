"""Builders for faprotax_weaver — how the weaver is assembled from its backends.

Two-builder convention (see weaverkit/docs/decisions.md C/D):

- ``build_faprotax_weaver()`` — the ZERO-CONFIG *introspection* builder that
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

from braidworks.core import BaseWeaver

from faprotax_weaver.backends.local import FaprotaxLocalBackend
from faprotax_weaver.weaver import FaprotaxWeaver


def build_faprotax_weaver(**_config: Any) -> BaseWeaver:
    """Zero-config introspection builder (``weaverkit verify``'s entry point).

    Wires every declared backend present-but-possibly-unconfigured. For real use,
    add a configured builder (see the module docstring / the commented skeletons).
    """
    backends = {
        "local": FaprotaxLocalBackend(),
    }
    return FaprotaxWeaver(backends)


# --- Optional builders (uncomment + fill in for real use) -----------------------
#
# A CONFIGURED builder — takes real config and raises if nothing is usable:
#
# from braidworks.core import BackendConfigurationError
#
# def build_faprotax_weaver_configured(**config: Any) -> BaseWeaver:
#     backends = {}
#     # ... wire backends from real config (paths / keys / clients) ...
#     if not backends:
#         raise BackendConfigurationError("configure at least one backend")
#     return FaprotaxWeaver(backends)
#
# A FIXTURE builder — only if no backend reads bundled/committed data; lets
# `weaverkit verify --strict` run golden against a tiny deterministic dataset
# (see decisions.md E and ncbi_weaver's build_faprotax_weaver_fixture):
#
# def build_faprotax_weaver_fixture() -> BaseWeaver:
#     ...  # return a weaver wired against a small synthesized/committed dataset
