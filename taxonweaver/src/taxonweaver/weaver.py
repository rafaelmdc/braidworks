"""NCBITaxonWeaver — the concrete Braidworks weaver for NCBI taxonomy."""

from __future__ import annotations

from braidworks.core import WeaverManifest

from . import vocab
from .backends.base import ResolutionBackend
from .dispatch import BackendDispatchWeaver


class NCBITaxonWeaver(BackendDispatchWeaver):
    """Resolves organism names/taxids via interchangeable ``local`` and ``api`` backends.

    The manifest declares whichever backends are actually wired in, so it never
    advertises a backend it cannot run. Construct via ``build_ncbi_weaver`` for
    the usual configuration-driven path.
    """

    def __init__(self, backends: dict[str, ResolutionBackend]) -> None:
        if not backends:
            raise ValueError("NCBITaxonWeaver requires at least one backend")
        super().__init__(backends)
        self.MANIFEST: WeaverManifest = vocab.build_manifest(
            backends=tuple(sorted(backends))
        )
