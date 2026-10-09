"""Matching is batch-local, detached and runs off the async event loop."""

import asyncio
import threading

import pytest
from faprotax_weaver.backends import local


async def test_identical_lineages_match_once_per_batch_and_remain_detached(monkeypatch):
    calls = []
    original = local._functional_groups

    def match(names):
        calls.append(names)
        return original(names)

    monkeypatch.setattr(local, "_functional_groups", match)
    backend = local.FaprotaxLocalBackend()
    queries = [{"ncbi.taxon.lineage": [name]} for name in ("Methylococcus", "methylococcus")]
    kwargs = {"requested_outputs": frozenset(), "groups_to_compute": frozenset()}
    records = await backend.fetch("describe_functions", queries, **kwargs)
    assert len(calls) == 1 and all(record.found for record in records)
    records[0].values[local._FUNCTIONAL_GROUPS].clear()
    assert records[1].values[local._FUNCTIONAL_GROUPS]
    assert (await backend.fetch("describe_functions", queries, **kwargs))[0].found
    assert len(calls) == 2  # no cross-batch query cache


def test_parsed_patterns_are_immutable():
    with pytest.raises(TypeError):
        local._load_groups()["injected"] = ()
    assert all(isinstance(patterns, tuple) for patterns in local._load_groups().values())


async def test_matching_releases_event_loop(monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def match(names):
        started.set()
        assert release.wait(5)
        return ["fixture"]

    monkeypatch.setattr(local, "_functional_groups", match)
    task = asyncio.create_task(
        local.FaprotaxLocalBackend().fetch(
            "describe_functions",
            [{"ncbi.taxon.lineage": ["fixture"]}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
    )
    try:
        assert await asyncio.to_thread(started.wait, 5)
        release.set()  # can run while the matching worker waits
        assert (await task)[0].found
    finally:
        release.set()
        await task
