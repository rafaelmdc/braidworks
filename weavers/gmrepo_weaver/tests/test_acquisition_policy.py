"""Acquisition limits apply across both stages and every retry attempt."""

import json
import sqlite3
import threading
import time
import urllib.error
from email.message import Message

import pytest
from gmrepo_weaver import setup
from gmrepo_weaver.acquisition import (
    AcquisitionPolicy,
    _AcquisitionClient,
    _CallBudgetExceeded,
    _map_workers,
)
from tests.test_acquisition_coverage import post


class Clock:
    now = 0.0

    def clock(self):
        return self.now

    def sleep(self, delay):
        self.now += delay


def test_policy_roundtrip_and_validation():
    policy = AcquisitionPolicy()
    assert AcquisitionPolicy.from_json(policy.to_json()) == policy
    for kwargs in [
        {"workers": True},
        {"max_calls": 0},
        {"max_attempts": 1.5},
        {"requests_per_second": float("nan")},
        {"requests_per_second": 0},
        {"retry_backoff": -1},
    ]:
        with pytest.raises(ValueError):
            AcquisitionPolicy(**kwargs)


def test_global_spacing_and_worker_bound():
    clock = Clock()
    active = peak = 0
    lock = threading.Lock()
    arrivals = []

    def transport(endpoint, body):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            arrivals.append(clock.now)
        try:
            time.sleep(0.01)
            return body
        finally:
            with lock:
                active -= 1

    policy = AcquisitionPolicy(workers=2, requests_per_second=2)
    client = _AcquisitionClient(transport, policy, clock=clock.clock, sleep=clock.sleep)
    results = list(
        _map_workers(
            range(6),
            lambda item: client("summary" if item < 3 else "profile", {"id": item}),
            workers=policy.workers,
        )
    )
    assert peak == 2 and active == 0
    assert arrivals == [0, 0.5, 1, 1.5, 2, 2.5]
    assert {item for item, _ in results} == set(range(6))


def test_retry_after_and_every_attempt_consume_budget():
    clock = Clock()
    arrivals = []
    headers = Message()
    headers["Retry-After"] = "2"

    def transport(endpoint, body):
        arrivals.append(clock.now)
        if len(arrivals) == 1:
            raise urllib.error.HTTPError("https://source", 429, "busy", headers, None)
        return []

    client = _AcquisitionClient(
        transport, AcquisitionPolicy(max_calls=2), clock=clock.clock, sleep=clock.sleep
    )
    assert client("summary", {}) == []
    assert arrivals == [0, 2] and client.retries == 1
    with pytest.raises(_CallBudgetExceeded):
        client("profile", {})
    assert client.calls == 2 and client.budget_exhausted


@pytest.mark.parametrize("status,expected_attempts", [(400, 1), (404, 1), (403, 1), (503, 3)])
def test_only_transient_http_failures_retry(status, expected_attempts):
    clock = Clock()
    calls = []

    def transport(*_):
        calls.append(clock.now)
        raise urllib.error.HTTPError("https://source", status, "failed", None, None)

    client = _AcquisitionClient(
        transport, AcquisitionPolicy(), clock=clock.clock, sleep=clock.sleep
    )
    with pytest.raises(urllib.error.HTTPError):
        client("summary", {})
    assert len(calls) == expected_attempts
    if status == 503:
        assert calls == [0, 1, 3]


def test_retry_after_beyond_waiting_budget_is_not_ignored():
    clock = Clock()
    headers = Message()
    headers["Retry-After"] = "120"
    calls = []

    def transport(*_):
        calls.append(clock.now)
        raise urllib.error.HTTPError("https://source", 429, "busy", headers, None)

    client = _AcquisitionClient(
        transport, AcquisitionPolicy(max_retry_delay=60), clock=clock.clock, sleep=clock.sleep
    )
    with pytest.raises(urllib.error.HTTPError):
        client("profile", {})
    assert len(calls) == 1


def test_budget_exhaustion_is_persisted_as_failed_coverage(tmp_path):
    def empty_transport(endpoint, body):
        if endpoint == setup._TAXON_ENDPOINT:
            return {"phenotypes_associated_with_taxon": []}
        return post(endpoint, body)

    target = tmp_path / "source.sqlite"
    setup._build(
        target,
        post=empty_transport,
        profile_phenotypes=["M"],
        acquisition_policy=AcquisitionPolicy(workers=1, requests_per_second=100000, max_calls=4),
    )
    with sqlite3.connect(target) as con:
        coverage = json.loads(
            con.execute("SELECT value FROM meta WHERE key='acquisition'").fetchone()[0]
        )
    assert coverage["requests"]["calls"] == 4
    assert coverage["requests"]["budget_exhausted"]
    assert coverage["taxa"]["3"]["status"] == "failed"
    assert coverage["profiles"]["M"]["status"] == "failed"
    assert not coverage["profiles"]["M"]["complete"]


def test_failed_catalog_budget_preserves_existing_database(tmp_path, monkeypatch):
    path = tmp_path / "source.sqlite"
    setup.write_db(path, overview=[{"ncbi_taxon_id": 1}], associations=[], phenotypes=[])
    original = path.read_bytes()
    monkeypatch.setattr(setup, "_post", post)
    # _build's injectable default is bound at import; explicitly supply the canned transport.
    original_build = setup._build

    def build(target, **kwargs):
        return original_build(target, post=post, **kwargs)

    monkeypatch.setattr(setup, "_build", build)
    with pytest.raises(_CallBudgetExceeded):
        setup.ensure_gmrepo_db(
            path, auto=True, refresh=True, acquisition_policy=AcquisitionPolicy(max_calls=1)
        )
    assert path.read_bytes() == original


def test_profile_work_is_reused_across_phenotype_stages():
    calls = []

    def transport(endpoint, body):
        calls.append(endpoint)
        if endpoint == setup._RUNS_ENDPOINT:
            return [{"run_id": "same"}]
        return {"species": [{"ncbi_taxon_id": 1, "relative_abundance": 2}], "genus": []}

    coverage = {}
    rows = setup._fetch_profiles(transport, ["A", "B", "A"], 2, coverage=coverage)
    assert calls.count(setup._RUNS_ENDPOINT) == 2
    assert calls.count(setup._PROFILE_ENDPOINT) == 1
    assert {row["mesh_id"] for row in rows} == {"A", "B"}
    assert all(scope["complete"] for scope in coverage.values())


def test_programming_fault_stops_submission_and_is_not_retried():
    calls = []

    def broken(item):
        calls.append(item)
        raise RuntimeError("bug")

    with pytest.raises(RuntimeError, match="bug"):
        list(_map_workers(range(1000), broken, workers=1))
    assert calls == [0]


def test_budget_does_not_count_a_retry_that_was_never_admitted():
    clock = Clock()

    def transport(*_):
        raise urllib.error.URLError("unavailable")

    client = _AcquisitionClient(
        transport, AcquisitionPolicy(max_calls=1), clock=clock.clock, sleep=clock.sleep
    )
    with pytest.raises(_CallBudgetExceeded):
        client("summary", {})
    assert client.calls == 1 and client.retries == 0
