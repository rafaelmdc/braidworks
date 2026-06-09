"""Minimal in-repo fakes so the Celery tests need neither Redis nor real weavers."""

from __future__ import annotations

from braidworks.core.braid import Braid, CapabilityInvocation, FallbackCondition
from braidworks.core.capability import Capability, OutputGroup, WeaverManifest
from braidworks.core.exceptions import BackendUnavailable
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import Strand, StrandSet
from braidworks.core.weaver import BaseWeaver

NAME = "organism.name"
TAXID = "ncbi.taxon.id"
CAP = "fake.resolve"


def _capability(backends: tuple[str, ...] = ("local",)) -> Capability:
    produces = frozenset({TAXID})
    return Capability(
        id=CAP,
        consumes=frozenset({NAME}),
        produces=produces,
        output_groups=(OutputGroup(id="g", outputs=produces),),
        backends=backends,
    )


class EchoWeaver(BaseWeaver):
    """Resolves ``organism.name`` to a deterministic fake taxid; counts batch calls."""

    def __init__(self, *, weaver_id: str = "fake", dataset: str = "ds-1") -> None:
        self._manifest = WeaverManifest(
            weaver_id=weaver_id, version="1.0.0", capabilities=(_capability(),)
        )
        self._dataset = dataset
        self.batch_calls = 0

    @property
    def MANIFEST(self) -> WeaverManifest:  # type: ignore[override]
        return self._manifest

    def backend_fingerprint(self, backend: str) -> str:
        return self._dataset

    async def execute(self, capability_id, strand_set, *, requested_outputs, backend):
        name = strand_set.get(NAME).value
        return WeaveResult(
            capability_id=capability_id,
            weaver_version="1.0.0",
            backend_used=backend,
            computed_groups=frozenset({"g"}),
            status=WeaveStatus.OK,
            strands=(Strand(TAXID, abs(hash(name)) % 100_000),),
        )

    async def execute_batch(self, capability_id, strand_sets, *, requested_outputs, backend):
        self.batch_calls += 1
        return [
            await self.execute(
                capability_id, ss, requested_outputs=requested_outputs, backend=backend
            )
            for ss in strand_sets
        ]


class FlakyWeaver(EchoWeaver):
    """Raises BackendUnavailable on ``unavailable_backend``; resolves on any other.

    Used to prove a backend control-exception raised *inside a worker* propagates
    back to the orchestrator, which then falls back to the next backend.
    """

    def __init__(self, *, unavailable_backend: str, **kw) -> None:
        super().__init__(**kw)
        self._manifest = WeaverManifest(
            weaver_id=self._manifest.weaver_id,
            version="1.0.0",
            capabilities=(_capability(("local", "api")),),
        )
        self._unavailable = unavailable_backend

    async def execute_batch(self, capability_id, strand_sets, *, requested_outputs, backend):
        if backend == self._unavailable:
            raise BackendUnavailable(f"{backend} down")
        return await super().execute_batch(
            capability_id, strand_sets, requested_outputs=requested_outputs, backend=backend
        )


def registry_with(weaver: BaseWeaver) -> BraidRegistry:
    reg = BraidRegistry()
    reg.register(weaver)
    return reg


def single_step_braid(
    weaver_id: str = "fake",
    *,
    primary: str = "local",
    fallback_backends: tuple[str, ...] = (),
    fallback_on: frozenset[FallbackCondition] = frozenset(),
) -> Braid:
    inv = CapabilityInvocation(
        weaver_id=weaver_id,
        capability_id=CAP,
        input_types=frozenset({NAME}),
        output_types=frozenset({TAXID}),
        primary_backend=primary,
        fallback_backends=fallback_backends,
        fallback_on=fallback_on,
    )
    return Braid(steps=(inv,), from_types=frozenset({NAME}), to_types=frozenset({TAXID}))


def name_sets(*names: str) -> list[StrandSet]:
    return [StrandSet.from_strands(f"e{i}", [Strand(NAME, n)]) for i, n in enumerate(names)]
