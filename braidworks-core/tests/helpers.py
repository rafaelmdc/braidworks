"""Shared test fixtures/builders mirroring the TaxonWeaver capability shape."""

from __future__ import annotations

from braidworks.core.capability import Capability, OutputGroup, WeaverManifest
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.weaver import BaseWeaver

CORE_OUTPUTS = frozenset(
    {
        "ncbi.taxon.id",
        "organism.scientific_name",
        "ncbi.taxon.rank",
        "ncbi.taxon.parent_id",
        "ncbi.taxon.match_type",
        "ncbi.taxon.review_required",
    }
)
LINEAGE_OUTPUTS = frozenset({"ncbi.taxon.lineage"})


def resolve_name_capability(
    *, backends: tuple[str, ...] = ("local",), max_batch_size: int | None = None
) -> Capability:
    """The ``ncbi.resolve_name`` capability: one input, core + lineage groups."""
    return Capability(
        id="ncbi.resolve_name",
        consumes=frozenset({"organism.name"}),
        produces=CORE_OUTPUTS | LINEAGE_OUTPUTS,
        output_groups=(
            OutputGroup(id="core", outputs=CORE_OUTPUTS),
            OutputGroup(id="lineage", outputs=LINEAGE_OUTPUTS),
        ),
        backends=backends,
        max_batch_size=max_batch_size,
    )


def manifest(*capabilities: Capability, weaver_id: str = "ncbi", version: str = "1.0.0") -> WeaverManifest:
    return WeaverManifest(weaver_id=weaver_id, version=version, capabilities=tuple(capabilities))


def simple_capability(
    cap_id: str,
    consumes: set[str],
    produces: set[str],
    *,
    backends: tuple[str, ...] = ("local",),
    cost: float = 1.0,
    max_batch_size: int | None = None,
) -> Capability:
    """A capability with a single output group ``g`` covering all produced types."""
    produces = frozenset(produces)
    return Capability(
        id=cap_id,
        consumes=frozenset(consumes),
        produces=produces,
        output_groups=(OutputGroup(id="g", outputs=produces),),
        backends=backends,
        cost=cost,
        max_batch_size=max_batch_size,
    )


class FakeWeaver(BaseWeaver):
    """A concrete weaver with an arbitrary manifest. ``execute`` is a stub.

    Phase 2 never executes; this exists so the registry/braider have real
    BaseWeaver instances and manifests to reason over.
    """

    def __init__(self, manifest_: WeaverManifest, *, dataset: str = "ds-fake") -> None:
        self._manifest = manifest_
        self._dataset = dataset

    # MANIFEST is normally a ClassVar; FakeWeaver carries it per-instance so a
    # single class can stand in for many distinct weavers in tests.
    @property
    def MANIFEST(self) -> WeaverManifest:  # type: ignore[override]
        return self._manifest

    def dataset_version(self) -> str:
        return self._dataset

    async def execute(self, capability_id, strand_set, *, requested_outputs, backend):
        return WeaveResult(
            capability_id=capability_id,
            capability_version=self._manifest.version,
            backend_used=backend,
            computed_groups=frozenset(),
            status=WeaveStatus.NO_MATCH,
        )


def make_weaver(
    *capabilities: Capability, weaver_id: str = "ncbi", version: str = "1.0.0"
) -> FakeWeaver:
    return FakeWeaver(manifest(*capabilities, weaver_id=weaver_id, version=version))
