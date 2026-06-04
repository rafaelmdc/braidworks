"""Shared test fixtures/builders mirroring the TaxonWeaver capability shape."""

from __future__ import annotations

from typing import Callable

from braidworks.core.braid import Braid, CapabilityInvocation, FallbackCondition
from braidworks.core.capability import Capability, OutputGroup, WeaverManifest
from braidworks.core.result import CandidateResult, WeaveResult, WeaveStatus
from braidworks.core.strand import Strand, StrandSet
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

    def backend_fingerprint(self, backend: str) -> str:
        return self._dataset

    async def execute(self, capability_id, strand_set, *, requested_outputs, backend):
        return WeaveResult(
            capability_id=capability_id,
            weaver_version=self._manifest.version,
            backend_used=backend,
            computed_groups=frozenset(),
            status=WeaveStatus.NO_MATCH,
        )


def make_weaver(
    *capabilities: Capability, weaver_id: str = "ncbi", version: str = "1.0.0"
) -> FakeWeaver:
    return FakeWeaver(manifest(*capabilities, weaver_id=weaver_id, version=version))


# --- Executor test scaffolding -------------------------------------------------

CAP_ID = "ncbi.resolve_name"
CAP_VERSION = "1.0.0"

# A resolver decides one entity's outcome given (strand_set, backend, requested).
Resolver = Callable[[StrandSet, str, frozenset], WeaveResult]


class ScriptedWeaver(BaseWeaver):
    """A weaver driven by a resolver callable, with call/size instrumentation.

    A resolver may *return* a WeaveResult (including NO_MATCH/AMBIGUOUS/ERROR) or
    *raise* a backend-level exception (BackendUnavailable / BackendConfigurationError)
    to simulate a whole-batch backend failure.
    """

    def __init__(
        self,
        resolver: Resolver,
        *,
        capability: Capability | None = None,
        weaver_id: str = "ncbi",
        version: str = CAP_VERSION,
        dataset: str = "ds-1",
    ) -> None:
        cap = capability if capability is not None else resolve_name_capability()
        self._manifest = manifest(cap, weaver_id=weaver_id, version=version)
        self._resolver = resolver
        self._dataset = dataset
        self.batch_calls = 0
        self.batch_sizes: list[int] = []

    @property
    def MANIFEST(self) -> WeaverManifest:  # type: ignore[override]
        return self._manifest

    def backend_fingerprint(self, backend: str) -> str:
        return self._dataset

    async def execute(self, capability_id, strand_set, *, requested_outputs, backend):
        return self._resolver(strand_set, backend, requested_outputs)

    async def execute_batch(self, capability_id, strand_sets, *, requested_outputs, backend):
        self.batch_calls += 1
        self.batch_sizes.append(len(strand_sets))
        return [self._resolver(ss, backend, requested_outputs) for ss in strand_sets]


def _groups_for(requested: frozenset[str]) -> frozenset[str]:
    """Mirror TaxonWeaver: requesting lineage computes core internally too."""
    if LINEAGE_OUTPUTS & requested:
        return frozenset({"core", "lineage"})
    return frozenset({"core"})


def ok_result(
    requested: frozenset[str],
    *strands: Strand,
    backend: str = "local",
    requires_review: bool = False,
    version: str = CAP_VERSION,
) -> WeaveResult:
    return WeaveResult(
        capability_id=CAP_ID,
        weaver_version=version,
        backend_used=backend,
        computed_groups=_groups_for(requested),
        status=WeaveStatus.OK,
        strands=tuple(strands),
        requires_review=requires_review,
    )


def no_match_result(requested: frozenset[str], *, backend: str = "local") -> WeaveResult:
    return WeaveResult(
        capability_id=CAP_ID,
        weaver_version=CAP_VERSION,
        backend_used=backend,
        computed_groups=_groups_for(requested),
        status=WeaveStatus.NO_MATCH,
    )


def ambiguous_result(
    requested: frozenset[str], *candidates: CandidateResult, backend: str = "local"
) -> WeaveResult:
    return WeaveResult(
        capability_id=CAP_ID,
        weaver_version=CAP_VERSION,
        backend_used=backend,
        computed_groups=_groups_for(requested),
        status=WeaveStatus.AMBIGUOUS,
        candidates=tuple(candidates),
        requires_review=True,
    )


def error_result(requested: frozenset[str], message: str, *, backend: str = "local") -> WeaveResult:
    return WeaveResult(
        capability_id=CAP_ID,
        weaver_version=CAP_VERSION,
        backend_used=backend,
        computed_groups=_groups_for(requested),
        status=WeaveStatus.ERROR,
        errors=(message,),
    )


def name_strand_sets(*names: str) -> list[StrandSet]:
    return [
        StrandSet.from_strands(f"e{i}", [Strand("organism.name", n)])
        for i, n in enumerate(names)
    ]


def single_step_braid(
    output_types: set[str],
    *,
    weaver_id: str = "ncbi",
    capability_id: str = CAP_ID,
    input_type: str = "organism.name",
    primary: str = "local",
    fallback_backends: tuple[str, ...] = (),
    fallback_on: frozenset[FallbackCondition] = frozenset(),
) -> Braid:
    inv = CapabilityInvocation(
        weaver_id=weaver_id,
        capability_id=capability_id,
        input_types=frozenset({input_type}),
        output_types=frozenset(output_types),
        primary_backend=primary,
        fallback_backends=fallback_backends,
        fallback_on=fallback_on,
    )
    return Braid(
        steps=(inv,),
        from_types=frozenset({input_type}),
        to_types=frozenset(output_types),
    )
