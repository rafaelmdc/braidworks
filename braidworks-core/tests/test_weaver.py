"""BaseWeaver: _reorder_by_key, abstract backend_fingerprint, default execute_batch."""

from __future__ import annotations

import pytest

from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import Strand, StrandSet
from braidworks.core.weaver import BaseWeaver

from helpers import manifest, resolve_name_capability


def _ok(name: str) -> WeaveResult:
    return WeaveResult(
        capability_id="ncbi.resolve_name",
        weaver_version="1.0.0",
        backend_used="local",
        computed_groups=frozenset({"core"}),
        status=WeaveStatus.OK,
        strands=(Strand("organism.scientific_name", name),),
    )


def _no_match(key: str) -> WeaveResult:
    return WeaveResult(
        capability_id="ncbi.resolve_name",
        weaver_version="1.0.0",
        backend_used="local",
        computed_groups=frozenset({"core"}),
        status=WeaveStatus.NO_MATCH,
    )


def test_reorder_fills_missing_with_no_match_in_order():
    original_keys = ["a", "b", "c", "d"]
    # Map arrives in a different order and is missing "b" and "d".
    results_map = {"c": _ok("C"), "a": _ok("A")}
    out = BaseWeaver._reorder_by_key(results_map, original_keys, _no_match)
    assert [r.status for r in out] == [
        WeaveStatus.OK,
        WeaveStatus.NO_MATCH,
        WeaveStatus.OK,
        WeaveStatus.NO_MATCH,
    ]
    assert out[0].strands[0].value == "A"
    assert out[2].strands[0].value == "C"


class _SerialWeaver(BaseWeaver):
    """Concrete weaver using the default serial execute_batch."""

    MANIFEST = manifest(resolve_name_capability())

    def backend_fingerprint(self, backend: str) -> str:
        return "ds-test"

    async def execute(self, capability_id, strand_set, *, requested_outputs, backend, params=None):
        return _ok(strand_set.get("organism.name").value)


async def test_default_execute_batch_one_per_input_in_order():
    w = _SerialWeaver()
    inputs = [
        StrandSet.from_strands(f"e{i}", [Strand("organism.name", n)])
        for i, n in enumerate(["a", "b", "c"])
    ]
    out = await w.execute_batch(
        "ncbi.resolve_name", inputs, requested_outputs=frozenset({"ncbi.taxon.id"}), backend="local"
    )
    assert len(out) == len(inputs)
    assert [r.strands[0].value for r in out] == ["a", "b", "c"]


def test_missing_backend_fingerprint_is_abstract():
    class NoVersionWeaver(BaseWeaver):
        MANIFEST = manifest(resolve_name_capability())

        async def execute(self, capability_id, strand_set, *, requested_outputs, backend, params=None):
            return _ok("x")

    with pytest.raises(TypeError):
        NoVersionWeaver()
