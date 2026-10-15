"""Tests for the shared weaver runtime: records, mappers, and dispatch."""

from __future__ import annotations

import pytest
from braidworks.core import (
    BackendBase,
    BackendDispatchWeaver,
    Candidate,
    Capability,
    LookupRecord,
    MatchStatus,
    OutputGroup,
    ResolverRecord,
    ReviewPolicy,
    Strand,
    StrandSet,
    WeaverManifest,
    WeaveStatus,
    map_lookup,
    map_resolver,
)
from braidworks.core.exceptions import BackendUnavailable, BraidworksError, UnsupportedCapability
from braidworks.core.executor import LocalExecutor
from braidworks.core.planner import Braider
from braidworks.core.registry import BraidRegistry

CAP = Capability(
    id="resolve",
    consumes=frozenset({"organism.name"}),
    produces=frozenset({"ncbi.taxon.id", "organism.scientific_name", "ncbi.taxon.rank"}),
    output_groups=(
        OutputGroup(id="core", outputs=frozenset({"ncbi.taxon.id", "organism.scientific_name"})),
        OutputGroup(id="rank", outputs=frozenset({"ncbi.taxon.rank"})),
    ),
    backends=("local",),
    always_computed_groups=frozenset({"core"}),
)


@pytest.mark.parametrize("count", [1, 3])
async def test_dispatch_rejects_wrong_record_count_before_mapping(count):
    class MalformedBackend(_StubBackend):
        async def fetch(self, capability_id, queries, **kwargs):
            return [LookupRecord(query={}, found=False) for _ in range(count)]

    weaver = _Weaver({"local": MalformedBackend()})
    inputs = [StrandSet.from_strands(str(i), [Strand("organism.name", str(i))]) for i in range(2)]
    with pytest.raises(BraidworksError, match="returned .* for 2 inputs"):
        await weaver.execute_batch(
            "resolve", inputs, requested_outputs=frozenset({"ncbi.taxon.id"}), backend="local"
        )


def _map_args(requested):
    return {
        "capability": CAP,
        "requested_outputs": requested,
        "backend": "local",
        "weaver_version": "1.0.0",
        "weaver_id": "ncbi",
    }


# --- mapper: lookup ----------------------------------------------------------


def test_lookup_hit_emits_only_allowed_outputs():
    rec = LookupRecord(
        query={}, found=True, values={"ncbi.taxon.id": 562, "ncbi.taxon.rank": "species"}
    )
    res = map_lookup(rec, **_map_args(frozenset({"ncbi.taxon.id"})))
    assert res.status is WeaveStatus.OK
    got = {s.type_id for s in res.strands}
    assert got == {"ncbi.taxon.id"}  # rank not requested -> filtered


def test_lookup_miss_is_no_match():
    res = map_lookup(LookupRecord(query={}, found=False), **_map_args(frozenset({"ncbi.taxon.id"})))
    assert res.status is WeaveStatus.NO_MATCH


def test_lookup_error_is_error():
    res = map_lookup(
        LookupRecord(query={}, error="boom"), **_map_args(frozenset({"ncbi.taxon.id"}))
    )
    assert res.status is WeaveStatus.ERROR and res.errors == ("boom",)
    assert res.computed_groups == frozenset()


def test_always_computed_group_in_computed_groups():
    # request only 'rank'; 'core' is always-computed -> both reported.
    res = map_lookup(
        LookupRecord(query={}, found=True), **_map_args(frozenset({"ncbi.taxon.rank"}))
    )
    assert "core" in res.computed_groups and "rank" in res.computed_groups


def test_provenance_uses_weaver_id_and_backend():
    rec = LookupRecord(query={}, found=True, values={"ncbi.taxon.id": 1})
    res = map_lookup(rec, **_map_args(frozenset({"ncbi.taxon.id"})))
    assert res.strands[0].provenance == ("ncbi:local",)


# --- mapper: resolver --------------------------------------------------------


def test_resolver_fuzzy_sets_requires_review():
    rec = ResolverRecord(
        query={}, status=MatchStatus.FUZZY_UNIQUE, score=88.0, values={"ncbi.taxon.id": 562}
    )
    res = map_resolver(rec, **_map_args(frozenset({"ncbi.taxon.id"})))
    assert res.status is WeaveStatus.OK and res.requires_review


def test_resolver_ambiguous_emits_candidates():
    rec = ResolverRecord(
        query={},
        status=MatchStatus.AMBIGUOUS,
        candidates=[
            Candidate(values={"ncbi.taxon.id": 1}, score=90.0),
            Candidate(values={"ncbi.taxon.id": 2}, score=80.0),
        ],
    )
    res = map_resolver(rec, **_map_args(frozenset({"ncbi.taxon.id"})))
    assert res.status is WeaveStatus.AMBIGUOUS and len(res.candidates) == 2 and res.requires_review


# --- dispatch ----------------------------------------------------------------


class _StubBackend(BackendBase):
    name = "local"

    def __init__(self, configured=True):
        self._configured = configured
        self.seen_groups = None

    def is_configured(self):
        return self._configured

    def fingerprint(self):
        return "stub-v1"

    async def fetch(
        self, capability_id, queries, *, requested_outputs, groups_to_compute, params=None
    ):
        self.seen_groups = groups_to_compute
        return [LookupRecord(query=q, found=True, values={"ncbi.taxon.id": 562}) for q in queries]


class _Weaver(BackendDispatchWeaver):
    MAPPER = staticmethod(map_lookup)

    def __init__(self, backends):
        super().__init__(backends)
        self.MANIFEST = WeaverManifest(weaver_id="ncbi", version="1.0.0", capabilities=(CAP,))


async def test_dispatch_routes_and_maps():
    w = _Weaver({"local": _StubBackend()})
    ss = StrandSet.from_strands("g", [Strand(type_id="organism.name", value="E. coli")])
    res = await w.execute(
        "resolve", ss, requested_outputs=frozenset({"ncbi.taxon.id"}), backend="local"
    )
    assert res.status is WeaveStatus.OK and res.strands[0].value == 562


async def test_dispatch_passes_groups_to_compute():
    backend = _StubBackend()
    w = _Weaver({"local": backend})
    ss = StrandSet.from_strands("g", [Strand(type_id="organism.name", value="x")])
    await w.execute(
        "resolve", ss, requested_outputs=frozenset({"ncbi.taxon.rank"}), backend="local"
    )
    assert backend.seen_groups == frozenset({"rank"})


async def test_dispatch_unconfigured_backend_raises():
    w = _Weaver({"local": _StubBackend(configured=False)})
    ss = StrandSet.from_strands("g", [Strand(type_id="organism.name", value="x")])
    with pytest.raises(BackendUnavailable):
        await w.execute(
            "resolve", ss, requested_outputs=frozenset({"ncbi.taxon.id"}), backend="local"
        )


async def test_dispatch_unknown_capability_raises():
    w = _Weaver({"local": _StubBackend()})
    ss = StrandSet.from_strands("g", [Strand(type_id="organism.name", value="x")])
    with pytest.raises(UnsupportedCapability):
        await w.execute("nope", ss, requested_outputs=frozenset(), backend="local")


def test_backend_fingerprint_guards_unconfigured():
    w = _Weaver({"local": _StubBackend(configured=False)})
    assert w.backend_fingerprint("local") == "unconfigured:local"
    assert w.backend_fingerprint("missing") == "unconfigured:missing"


def test_empty_backends_rejected():
    with pytest.raises(ValueError, match="at least one backend"):
        _Weaver({})


@pytest.mark.parametrize(
    "first,second",
    [
        ("ncbi.taxon.rank", "ncbi.taxon.id"),
        ("ncbi.taxon.id", "ncbi.taxon.rank"),
    ],
)
@pytest.mark.parametrize("kind", ["lookup", "resolved", "ambiguous"])
async def test_cache_reuses_emitted_groups_without_claiming_internal_outputs(first, second, kind):
    class Backend(_StubBackend):
        calls = 0

        async def fetch(self, capability_id, queries, **kwargs):
            self.calls += 1
            values = {
                "ncbi.taxon.id": 562,
                "organism.scientific_name": "Escherichia coli",
                "ncbi.taxon.rank": "species",
            }
            if kind == "lookup":
                return [LookupRecord(query=q, found=True, values=values) for q in queries]
            if kind == "resolved":
                return [
                    ResolverRecord(query=q, status=MatchStatus.RESOLVED, values=values)
                    for q in queries
                ]
            return [
                ResolverRecord(
                    query=q,
                    status=MatchStatus.AMBIGUOUS,
                    candidates=[Candidate(values=values, score=1.0)],
                )
                for q in queries
            ]

    class Weaver(_Weaver):
        MAPPER = staticmethod(map_lookup if kind == "lookup" else map_resolver)

    backend = Backend()
    registry = BraidRegistry()
    registry.register(Weaver({"local": backend}))
    executor = LocalExecutor(registry)

    async def run(target, runner):
        inputs = [StrandSet.from_strands("e1", [Strand("organism.name", "E. coli")])]
        braid = Braider(registry).plan(
            available_types=frozenset({"organism.name"}), target_types=frozenset({target})
        )
        return await runner.execute(braid, inputs, review_policy=ReviewPolicy.ALLOW_CONTINUE)

    first_result = await run(first, executor)
    assert first_result.resolved[0].available_types() == (
        frozenset({"organism.name"}) | CAP.outputs_to_compute(frozenset({first}))
    )
    second_result = await run(second, executor)
    assert len(second_result.resolved) == 1
    assert backend.calls == 2
    repeated = await run(second, executor)
    assert backend.calls == 2
    fresh = await run(second, LocalExecutor(registry))
    assert second_result.resolved[0].get(second) == fresh.resolved[0].get(second)
    assert repeated.resolved[0].get(second) == fresh.resolved[0].get(second)


async def test_cache_retains_triggered_group_when_optional_outputs_are_absent():
    class Backend(_StubBackend):
        calls = 0

        async def fetch(self, capability_id, queries, **kwargs):
            self.calls += 1
            return [
                LookupRecord(query=q, found=True, values={"ncbi.taxon.rank": None}) for q in queries
            ]

    backend = Backend()
    registry = BraidRegistry()
    registry.register(_Weaver({"local": backend}))
    executor = LocalExecutor(registry)
    braid = Braider(registry).plan(
        available_types=frozenset({"organism.name"}),
        target_types=frozenset({"ncbi.taxon.rank"}),
    )
    for _ in range(2):
        result = await executor.execute(
            braid, [StrandSet.from_strands("e1", [Strand("organism.name", "E. coli")])]
        )
        assert len(result.unresolved) == 1
    assert backend.calls == 1


@pytest.mark.parametrize("found,error", [(True, None), (False, None), (False, "failed")])
def test_lookup_source_warnings_survive_mapping_and_json(found, error):
    record = LookupRecord(
        query={"id": 1}, found=found, error=error, warnings=("source coverage incomplete",)
    )
    restored = LookupRecord.from_json(record.to_json())
    assert restored == record
    result = map_lookup(restored, **_map_args(frozenset({"ncbi.taxon.id"})))
    assert result.warnings == record.warnings
    assert type(result).from_json(result.to_json()).warnings == record.warnings


def test_resolver_error_does_not_claim_requested_or_always_computed_groups():
    result = map_resolver(
        ResolverRecord(query={}, status=MatchStatus.ERROR, error="unavailable"),
        **_map_args(frozenset({"ncbi.taxon.rank"})),
    )
    assert result.status is WeaveStatus.ERROR
    assert result.computed_groups == frozenset()


async def test_dispatch_rejects_backend_not_supported_by_capability():
    class NeverFetch(_StubBackend):
        async def fetch(self, *args, **kwargs):
            raise AssertionError("unsupported backend must not fetch")

    weaver = _Weaver({"local": NeverFetch(), "api": NeverFetch()})
    with pytest.raises(BackendUnavailable, match="not supported"):
        await weaver.execute_batch("resolve", [], requested_outputs=frozenset(), backend="api")
