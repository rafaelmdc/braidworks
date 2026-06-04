"""The contract-test mixins themselves.

These are framework-light: a subclass provides a few attributes/methods and
pytest collects the ``test_*`` methods. They assume the weaver is deterministic
for a given input (true for a versioned local DB), so a batch result can be
compared against the corresponding single-item result.
"""

from __future__ import annotations

from typing import Any

from braidworks.core.cache import InMemoryStrandCache, compute_cache_key
from braidworks.core.capability import Capability
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import Strand, StrandSet
from braidworks.core.weaver import BaseWeaver


def _hashable(value: Any) -> Any:
    """Make a strand value comparable/orderable for signatures."""
    if isinstance(value, list):
        return tuple(_hashable(v) for v in value)
    if isinstance(value, dict):
        return tuple(sorted((k, _hashable(v)) for k, v in value.items()))
    return value


def _signature(result: WeaveResult) -> tuple:
    """A stable identity for a result: status + its (type_id, value) strands.

    Avoids comparing volatile fields (confidence floats, metadata) so the order
    contract is about *which* result lands where, not byte-equality.
    """
    strands = tuple(sorted((s.type_id, _hashable(s.value)) for s in result.strands))
    return (result.status, strands)


class WeaverOrderContractTests:
    """Verifies execute_batch's order/length contract.

    Subclass and provide:
      - ``capability_id: str``
      - ``minimal_outputs: frozenset[str]``
      - ``backend: str`` (optional, defaults to ``"local"``)
      - ``make_weaver(self) -> BaseWeaver``
      - ``sample_strand_sets(self) -> list[StrandSet]`` (>= 5 distinct inputs)
    """

    capability_id: str
    minimal_outputs: frozenset[str]
    backend: str = "local"

    def make_weaver(self) -> BaseWeaver:  # pragma: no cover - overridden
        raise NotImplementedError

    def sample_strand_sets(self) -> list[StrandSet]:  # pragma: no cover - overridden
        raise NotImplementedError

    async def _batch(self, weaver: BaseWeaver, strand_sets: list[StrandSet]) -> list[WeaveResult]:
        return await weaver.execute_batch(
            self.capability_id,
            strand_sets,
            requested_outputs=self.minimal_outputs,
            backend=self.backend,
        )

    def test_at_least_five_distinct_samples(self):
        samples = self.sample_strand_sets()
        assert len(samples) >= 5, "provide at least 5 sample strand sets"
        fingerprints = {
            tuple(sorted((t, _hashable(s.value)) for t, s in ss._strands.items()))
            for ss in samples
        }
        assert len(fingerprints) == len(samples), "sample inputs must be distinct"

    async def test_one_result_per_input(self):
        weaver = self.make_weaver()
        samples = self.sample_strand_sets()
        out = await self._batch(weaver, samples)
        assert len(out) == len(samples)

    async def test_results_correspond_to_inputs(self):
        weaver = self.make_weaver()
        samples = self.sample_strand_sets()
        batch = await self._batch(weaver, samples)
        for i, ss in enumerate(samples):
            single = await weaver.execute(
                self.capability_id,
                ss,
                requested_outputs=self.minimal_outputs,
                backend=self.backend,
            )
            assert _signature(batch[i]) == _signature(single)

    async def test_reversing_input_reverses_output(self):
        weaver = self.make_weaver()
        samples = self.sample_strand_sets()
        forward = await self._batch(weaver, samples)
        reverse = await self._batch(weaver, list(reversed(samples)))
        assert [_signature(r) for r in reverse] == [
            _signature(r) for r in reversed(forward)
        ]


class CacheFingerprintTests:
    """Verifies cache key/fingerprint rules for a capability.

    Subclass and provide:
      - ``capability: Capability``
      - ``consumed_values_a: dict[str, Any]`` covering ``capability.consumes``
      - ``consumed_values_b: dict[str, Any]`` same keys, at least one value differs
      - ``group_subset: str`` (default ``"core"``) — a group id of the capability
      - ``group_superset: str`` (default ``"lineage"``) — a second group id
    """

    capability: Capability
    consumed_values_a: dict[str, Any]
    consumed_values_b: dict[str, Any]
    group_subset: str = "core"
    group_superset: str = "lineage"

    def _ss(self, values: dict[str, Any], *, provenance: tuple[str, ...] = (), extra: bool = False) -> StrandSet:
        strands = [Strand(t, v, provenance=provenance) for t, v in values.items()]
        if extra:
            strands.append(Strand("zzz.unrelated.note", "ignore me"))
        return StrandSet.from_strands("e", strands)

    def _key(
        self,
        strand_set: StrandSet,
        *,
        weaver_id: str = "w",
        weaver_version: str = "1",
        backend: str = "local",
        backend_fingerprint: str = "ds-1",
    ):
        return compute_cache_key(
            self.capability,
            strand_set,
            weaver_id=weaver_id,
            weaver_version=weaver_version,
            backend=backend,
            backend_fingerprint=backend_fingerprint,
        )

    def _result(self, computed_groups: set[str]) -> WeaveResult:
        return WeaveResult(
            capability_id=self.capability.id,
            weaver_version="1",
            backend_used="local",
            computed_groups=frozenset(computed_groups),
            status=WeaveStatus.OK,
        )

    def test_provenance_excluded_from_fingerprint(self):
        a = self._ss(self.consumed_values_a, provenance=("src_a",))
        b = self._ss(self.consumed_values_a, provenance=("src_b",))
        assert self._key(a).input_fingerprint == self._key(b).input_fingerprint

    def test_different_value_different_fingerprint(self):
        a = self._ss(self.consumed_values_a)
        b = self._ss(self.consumed_values_b)
        assert self._key(a).input_fingerprint != self._key(b).input_fingerprint

    def test_extra_strands_do_not_change_fingerprint(self):
        minimal = self._ss(self.consumed_values_a)
        extended = self._ss(self.consumed_values_a, extra=True)
        assert self._key(minimal).input_fingerprint == self._key(extended).input_fingerprint

    def test_requested_groups_do_not_affect_key(self):
        ss = self._ss(self.consumed_values_a)
        # The key has no group input at all, so repeated computation is identical.
        assert self._key(ss) == self._key(ss)

    def test_backend_fingerprint_changes_key(self):
        ss = self._ss(self.consumed_values_a)
        assert self._key(ss, backend_fingerprint="ds-1") != self._key(ss, backend_fingerprint="ds-2")

    def test_weaver_version_changes_key(self):
        ss = self._ss(self.consumed_values_a)
        assert self._key(ss, weaver_version="1") != self._key(ss, weaver_version="2")

    def test_weaver_id_changes_key(self):
        ss = self._ss(self.consumed_values_a)
        assert self._key(ss, weaver_id="w1") != self._key(ss, weaver_id="w2")

    def test_backend_changes_key(self):
        ss = self._ss(self.consumed_values_a)
        assert self._key(ss, backend="local") != self._key(ss, backend="api")

    def test_superset_groups_satisfy_lookup(self):
        cache = InMemoryStrandCache()
        key = self._key(self._ss(self.consumed_values_a))
        cache.put(key, self._result({self.group_subset, self.group_superset}))
        assert cache.get(key, frozenset({self.group_subset})) is not None

    def test_subset_groups_do_not_satisfy_superset_lookup(self):
        cache = InMemoryStrandCache()
        key = self._key(self._ss(self.consumed_values_a))
        cache.put(key, self._result({self.group_subset}))
        assert cache.get(key, frozenset({self.group_subset, self.group_superset})) is None

    def test_two_group_sets_store_two_entries(self):
        cache = InMemoryStrandCache()
        key = self._key(self._ss(self.consumed_values_a))
        cache.put(key, self._result({self.group_subset}))
        cache.put(key, self._result({self.group_subset, self.group_superset}))
        # Both are retrievable by the appropriate requested groups.
        assert cache.get(key, frozenset({self.group_subset})) is not None
        rich = cache.get(key, frozenset({self.group_subset, self.group_superset}))
        assert rich is not None
        assert rich.computed_groups == frozenset({self.group_subset, self.group_superset})
