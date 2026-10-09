"""Semantic source policies cannot share incompatible cached results."""

import httpx
import pytest
from braidworks.core import Strand, StrandSet
from braidworks.core.cache import InMemoryStrandCache
from braidworks.core.executor import LocalExecutor
from braidworks.core.planner import Braider
from braidworks.core.registry import BraidRegistry
from braidworks.core.sqlite_cache import SQLiteStrandCache
from quickgo_weaver.backends.api import QuickgoApiBackend
from quickgo_weaver.factory import build_quickgo_weaver
from quickgo_weaver.fixture import _handler
from quickgo_weaver.weaver import QuickgoWeaver


@pytest.mark.parametrize("persistent", [False, True])
async def test_limit_and_effective_injected_endpoint_separate_cache(tmp_path, persistent):
    cache = SQLiteStrandCache(tmp_path / "cache") if persistent else InMemoryStrandCache()
    calls = []

    async def track(request):
        calls.append(str(request.url))

    for endpoint, budget in [
        ("https://first/api", 1),
        ("https://first/api", 2),
        ("https://second/api", 2),
    ]:
        async with httpx.AsyncClient(
            base_url=endpoint,
            transport=httpx.MockTransport(_handler),
            event_hooks={"request": [track]},
        ) as client:
            backend = QuickgoApiBackend(client=client, max_pages=budget)
            registry = BraidRegistry()
            registry.register(QuickgoWeaver({"api": backend}))
            executor = LocalExecutor(registry, cache=cache)
            braid = Braider(registry).plan(
                frozenset({"protein.uniprot.accession"}), frozenset({"go.count"})
            )
            inputs = [
                StrandSet.from_strands("protein", [Strand("protein.uniprot.accession", "P04637")])
            ]
            before = len(calls)
            result = await executor.execute(braid, inputs)
            assert result.resolved and len(calls) > before
            after = len(calls)
            await executor.execute(braid, inputs)
            assert len(calls) == after


@pytest.mark.parametrize("value", [True, 0, -1, 1.5])
def test_semantic_budget_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        QuickgoApiBackend(max_pages=value)


def test_endpoint_secrets_are_not_emitted_and_builder_honors_policy():
    first = QuickgoApiBackend(
        base_url="https://user:secret@first/api?token=private", max_pages=1
    ).fingerprint()
    second = QuickgoApiBackend(base_url="https://second/api", max_pages=1).fingerprint()
    assert first != second and "secret" not in first and "private" not in first
    weaver = build_quickgo_weaver(base_url="https://second/api", max_pages=1)
    assert weaver._backends["api"].fingerprint() == second
