"""In-repo fakes so the arq tests need neither Redis nor real weavers."""

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
TRAIT = "microbe.trait.gram_stain"
DIS = "disease.assoc"


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
    """Raises BackendUnavailable on ``unavailable_backend``; resolves on any other."""

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


# --- branch graph (name -> taxid -> {trait, disease}) for distributed parallelism ---


def _one_cap(cid: str, consume: str, produce: str) -> Capability:
    prod = frozenset({produce})
    return Capability(
        id=cid,
        consumes=frozenset({consume}),
        produces=prod,
        output_groups=(OutputGroup(id="g", outputs=prod),),
        backends=("local",),
    )


class _Fn(BaseWeaver):
    def __init__(self, weaver_id, cap, out_type, *, miss=False):
        self._m = WeaverManifest(weaver_id=weaver_id, version="1.0.0", capabilities=(cap,))
        self._out = out_type
        self._miss = miss

    @property
    def MANIFEST(self):  # type: ignore[override]
        return self._m

    def backend_fingerprint(self, backend):
        return "ds"

    async def execute(self, capability_id, strand_set, *, requested_outputs, backend):
        status = WeaveStatus.NO_MATCH if self._miss else WeaveStatus.OK
        strands = () if self._miss else (Strand(self._out, f"{self._out}:ok"),)
        return WeaveResult(
            capability_id=capability_id,
            weaver_version="1.0.0",
            backend_used=backend,
            computed_groups=frozenset({"g"}),
            status=status,
            strands=strands,
        )


def branch_registry(*, disease_miss: bool = False) -> BraidRegistry:
    """name->taxid (ncbi), then independent taxid->trait (bacdive) + taxid->disease (disbiome)."""
    reg = BraidRegistry()
    reg.register(_Fn("ncbi", _one_cap("ncbi.resolve", NAME, TAXID), TAXID))
    reg.register(_Fn("bacdive", _one_cap("bacdive.traits", TAXID, TRAIT), TRAIT))
    reg.register(_Fn("disbiome", _one_cap("disbiome.assoc", TAXID, DIS), DIS, miss=disease_miss))
    return reg


# --- inline arq pool double (runs weave_step in-process, no Redis) ---


class InlineJob:
    def __init__(self, fn, args, redis) -> None:
        self._fn = fn
        self._args = args
        self._redis = redis

    async def result(self, timeout=None):
        ctx = {"job_try": 1, "redis": self._redis}
        return await self._fn(ctx, *self._args)


class InlinePool:
    """Mimics ``ArqRedis.enqueue_job`` by running the task coroutine inline."""

    def __init__(self, fn, *, redis=None) -> None:
        self._fn = fn
        self._redis = redis

    async def enqueue_job(self, name, *args, _queue_name=None, **kw):
        return InlineJob(self._fn, args, self._redis)
