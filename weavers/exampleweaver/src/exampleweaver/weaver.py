"""ExampleWeaver — the concrete Braidworks weaver for Example reference weaver (taxid -> traits, from a tiny CSV)."""

from __future__ import annotations

from braidworks.core import WeaverManifest

from exampleweaver import vocab
from exampleweaver.backends.base import ExampleBackend
from exampleweaver.dispatch import BackendDispatchWeaver


class ExampleWeaver(BackendDispatchWeaver):
    """Resolves inputs via the wired-in backends. The manifest declares only those."""

    def __init__(self, backends: dict[str, ExampleBackend]) -> None:
        if not backends:
            raise ValueError("ExampleWeaver requires at least one backend")
        super().__init__(backends)
        self.MANIFEST: WeaverManifest = vocab.build_manifest(backends=tuple(sorted(backends)))
