"""Branch parallelism: independent braid branches run concurrently; NO_MATCH on one
branch is local (the entity is still resolved), with per-step completion metadata."""

from __future__ import annotations

import asyncio

from braidworks.core.braid import Braid, BackendPolicy, CapabilityInvocation
from braidworks.core.capability import Capability, OutputGroup, WeaverManifest
from braidworks.core.executor import LocalExecutor
from braidworks.core.planner import Braider
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import Strand, StrandSet
from braidworks.core.weaver import BaseWeaver

NAME = "organism.name"
TAXID = "ncbi.taxon.id"
TRAIT = "microbe.trait.gram_stain"
DIS = "disease.assoc"


def _cap(cid: str, consume: str, produce: str) -> Capability:
    prod = frozenset({produce})
    return Capability(
        id=cid,
        consumes=frozenset({consume}),
        produces=prod,
        output_groups=(OutputGroup(id="g", outputs=prod),),
        backends=("local",),
    )


def _ok(cid: str, *strands: Strand) -> WeaveResult:
    return WeaveResult(
        capability_id=cid,
        weaver_version="1.0.0",
        backend_used="local",
        computed_groups=frozenset({"g"}),
        status=WeaveStatus.OK,
        strands=tuple(strands),
    )


def _no_match(cid: str) -> WeaveResult:
    return WeaveResult(
        capability_id=cid,
        weaver_version="1.0.0",
        backend_used="local",
        computed_groups=frozenset({"g"}),
        status=WeaveStatus.NO_MATCH,
    )


class FnWeaver(BaseWeaver):
    """A weaver whose batch is an async callable ``fn(strand_set, backend)``."""

    def __init__(self, weaver_id: str, capability: Capability, fn) -> None:
        self._m = WeaverManifest(weaver_id=weaver_id, version="1.0.0", capabilities=(capability,))
        self._fn = fn
        self.calls = 0

    @property
    def MANIFEST(self) -> WeaverManifest:  # type: ignore[override]
        return self._m

    def backend_fingerprint(self, backend: str) -> str:
        return "ds"

    async def execute(self, capability_id, strand_set, *, requested_outputs, backend, params=None):
        self.calls += 1
        return await self._fn(strand_set, backend)


def _branch_registry(traits_fn, disease_fn) -> BraidRegistry:
    reg = BraidRegistry()

    async def name_to_taxid(ss, backend):
        return _ok("ncbi.resolve", Strand(TAXID, abs(hash(ss.get(NAME).value)) % 100_000))

    reg.register(FnWeaver("ncbi", _cap("ncbi.resolve", NAME, TAXID), name_to_taxid))
    reg.register(FnWeaver("bacdive", _cap("bacdive.traits", TAXID, TRAIT), traits_fn))
    reg.register(FnWeaver("disbiome", _cap("disbiome.assoc", TAXID, DIS), disease_fn))
    return reg


def _branch_braid() -> Braid:
    return Braider(_branch_registry(None, None)).plan(
        frozenset({NAME}), frozenset({TRAIT, DIS}), backend_policy=BackendPolicy.LOCAL_ONLY
    )


def _name_set(name: str = "ecoli") -> list[StrandSet]:
    return [StrandSet.from_strands("e0", [Strand(NAME, name)])]


# --- waves --------------------------------------------------------------------


def test_waves_group_independent_branches():
    braid = _branch_braid()
    waves = braid.waves()
    # ncbi resolves first (its own wave); the two taxid-consuming branches share one.
    assert len(waves) == 2
    assert len(waves[0]) == 1
    assert len(waves[1]) == 2


def test_waves_linear_chain_is_one_step_per_wave():
    a = CapabilityInvocation("w", "a", frozenset({NAME}), frozenset({TAXID}), "local")
    b = CapabilityInvocation("w", "b", frozenset({TAXID}), frozenset({TRAIT}), "local")
    braid = Braid(steps=(a, b), from_types=frozenset({NAME}), to_types=frozenset({TRAIT}))
    assert braid.waves() == ((0,), (1,))


# --- concurrency --------------------------------------------------------------


async def test_independent_branches_run_concurrently():
    """Both branches reach a shared barrier at once — a sequential executor would hang."""
    barrier = asyncio.Barrier(2)

    async def gated(cid, out_type):
        async def fn(ss, backend):
            await asyncio.wait_for(barrier.wait(), timeout=2.0)
            return _ok(cid, Strand(out_type, f"{out_type}:{ss.get(TAXID).value}"))

        return fn

    reg = _branch_registry(await gated("bacdive.traits", TRAIT), await gated("disbiome.assoc", DIS))
    ex = LocalExecutor(reg)
    res = await ex.execute(_branch_braid(), _name_set())
    assert len(res.resolved) == 1
    got = res.resolved[0]
    assert got.has(TRAIT) and got.has(DIS)


# --- partial success + completion metadata ------------------------------------


async def test_partial_branch_success_is_resolved_with_completion():
    async def traits_ok(ss, backend):
        return _ok("bacdive.traits", Strand(TRAIT, "positive"))

    async def disease_miss(ss, backend):
        return _no_match("disbiome.assoc")

    reg = _branch_registry(traits_ok, disease_miss)
    ex = LocalExecutor(reg)
    res = await ex.execute(_branch_braid(), _name_set())

    # One branch produced data, the other did not → still resolved (lenient).
    assert len(res.resolved) == 1
    assert res.unresolved == []
    ss = res.resolved[0]
    assert ss.has(TRAIT) and not ss.has(DIS)
    outcomes = {o.capability_id: o.status for o in ss.completion}
    assert outcomes["ncbi.resolve"] == "ok"
    assert outcomes["bacdive.traits"] == "ok"
    assert outcomes["disbiome.assoc"] == "no_match"


async def test_no_targets_on_any_branch_is_unresolved():
    async def miss(ss, backend):
        return _no_match("x")

    reg = _branch_registry(miss, miss)
    ex = LocalExecutor(reg)
    res = await ex.execute(_branch_braid(), _name_set())
    assert len(res.resolved) == 0
    assert len(res.unresolved) == 1


async def test_root_no_match_skips_dependent_branches():
    """If name→taxid misses, both taxid branches are skipped (input-gated), not errored."""
    reg = _branch_registry(None, None)
    # Replace the root weaver with one that never resolves.
    reg = BraidRegistry()

    async def root_miss(ss, backend):
        return _no_match("ncbi.resolve")

    async def trait_ok(ss, backend):
        return _ok("bacdive.traits", Strand(TRAIT, "positive"))

    reg.register(FnWeaver("ncbi", _cap("ncbi.resolve", NAME, TAXID), root_miss))
    reg.register(FnWeaver("bacdive", _cap("bacdive.traits", TAXID, TRAIT), trait_ok))
    reg.register(FnWeaver("disbiome", _cap("disbiome.assoc", TAXID, DIS), trait_ok))
    braid = Braider(reg).plan(
        frozenset({NAME}), frozenset({TRAIT, DIS}), backend_policy=BackendPolicy.LOCAL_ONLY
    )
    ex = LocalExecutor(reg)
    res = await ex.execute(braid, _name_set())
    assert len(res.unresolved) == 1
    ss = res.unresolved[0][0]
    outcomes = {o.capability_id: o.status for o in ss.completion}
    assert outcomes["ncbi.resolve"] == "no_match"
    assert outcomes["bacdive.traits"] == "skipped"
    assert outcomes["disbiome.assoc"] == "skipped"
