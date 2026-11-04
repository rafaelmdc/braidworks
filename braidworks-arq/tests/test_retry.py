"""Explicit worker retry policy, bounded attempts and normal result preservation."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from arq.worker import Retry
from braidworks.core.exceptions import (
    BackendConfigurationError,
    BackendUnavailable,
    BatchContractError,
    UnsupportedCapability,
)
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks_arq import discovery, tasks
from braidworks_arq.retry import should_retry
from fakes import TAXID, EchoWeaver, name_sets, registry_with
from redis.exceptions import AuthenticationError, AuthorizationError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

TRANSIENTS = [
    TimeoutError(),
    ConnectionError("disconnected"),
    RedisConnectionError("broker down"),
    RedisTimeoutError(),
    httpx.ReadTimeout(""),
    httpx.ConnectError(""),
]
NONRETRYABLE = [
    AuthenticationError("bad Redis credentials"),
    AuthorizationError("Redis permission denied"),
    BackendUnavailable("not configured"),
    BackendConfigurationError("bad configuration"),
    UnsupportedCapability("unknown capability"),
    BatchContractError("wrong batch length"),
    TypeError("timeout"),
    ValueError("network failed"),
    KeyError("missing field"),
    AssertionError("invariant"),
    NotImplementedError("stub"),
    RuntimeError("upstream hiccup"),
    PermissionError("permission denied"),
    FileNotFoundError("missing local data"),
    httpx.HTTPStatusError(
        "upstream 503",
        request=httpx.Request("GET", "https://example.test"),
        response=httpx.Response(503),
    ),
]


@pytest.mark.parametrize("exc", TRANSIENTS + NONRETRYABLE)
@pytest.mark.parametrize("job_try", [1, 2, tasks.MAX_TRIES])
async def test_worker_attempts_follow_explicit_policy(monkeypatch, exc, job_try):
    calls = []

    class Broken(EchoWeaver):
        async def execute_batch(self, *args, **kwargs):
            calls.append(kwargs)
            raise exc

    discovery.set_registry(registry_with(Broken()))
    monkeypatch.setattr(tasks.random, "random", lambda: 0.25)
    retryable = any(exc is transient for transient in TRANSIENTS)
    assert should_retry(exc) is retryable
    payload = [ss.to_json() for ss in name_sets("x", "y")]
    if retryable and job_try < tasks.MAX_TRIES:
        with pytest.raises(Retry) as caught:
            await tasks.weave_step(
                {"job_try": job_try, "redis": None},
                "fake",
                "fake.resolve",
                "local",
                payload,
                [TAXID],
                {"threshold": 0.8},
            )
        assert caught.value.defer_score == 1000 * (2 ** (job_try - 1)) * 0.75
        assert caught.value.__cause__ is exc
    else:
        with pytest.raises(type(exc)) as caught:
            await tasks.weave_step(
                {"job_try": job_try, "redis": None},
                "fake",
                "fake.resolve",
                "local",
                payload,
                [TAXID],
                {"threshold": 0.8},
            )
        assert caught.value is exc
    assert len(calls) == 1
    assert calls[0]["params"] == {"threshold": 0.8}


@pytest.mark.parametrize("status", [WeaveStatus.NO_MATCH, WeaveStatus.ERROR])
async def test_normal_failure_values_are_returned_without_retry(status):
    class ResultWeaver(EchoWeaver):
        async def execute_batch(self, capability_id, strand_sets, **kwargs):
            self.batch_calls += 1
            return [
                WeaveResult(
                    capability_id=capability_id,
                    weaver_version="1.0.0",
                    backend_used="local",
                    status=status,
                    computed_groups=frozenset(),
                    errors=("timeout upstream 503",),
                )
                for _ in strand_sets
            ]

    weaver = ResultWeaver()
    discovery.set_registry(registry_with(weaver))
    output = await tasks.weave_step(
        {"redis": None},
        "fake",
        "fake.resolve",
        "local",
        [ss.to_json() for ss in name_sets("x", "y")],
        [TAXID],
    )
    assert len(output) == 2
    assert all(result["status"] == status.value for result in output)
    assert weaver.batch_calls == 1


async def test_worker_cancellation_propagates():
    class Cancelled(EchoWeaver):
        async def execute_batch(self, *args, **kwargs):
            raise asyncio.CancelledError()

    discovery.set_registry(registry_with(Cancelled()))
    with pytest.raises(asyncio.CancelledError):
        await tasks.weave_step(
            {"redis": None},
            "fake",
            "fake.resolve",
            "local",
            [ss.to_json() for ss in name_sets("x")],
            [TAXID],
        )
