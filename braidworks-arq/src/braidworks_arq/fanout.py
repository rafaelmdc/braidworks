"""Entity-level fan-out planning: split a step's batch across workers, safely.

**Not to be confused with cardinality fan-out.** This module splits a *batch of N
inputs* across workers for throughput — it never turns one input into many. Core's
*cardinality* fan-out (``ExpandPolicy`` / a capability's ``set_outputs``) is the one→many
expansion, and it lives entirely in ``LocalExecutor``'s orchestration — which
``build_distributed_executor`` reuses verbatim — so it works unchanged when steps run on
workers. The two **compose**: batch-parallelism (here) × cardinality-expansion (core).
See ``braidworks-arq/tests/test_fanout.py::test_cardinality_fanout_through_distributed_executor``.

Fan-out is **opt-in per ``weaver:backend``** and **gated on a rate budget**, so it can
never cause an uncontrolled API rate-storm. The dangerous case — fanning a rate-limited
external backend out across many workers with no budget — is refused loudly with
:class:`FanoutConfigError` rather than silently degraded.

Environment:

- ``BRAIDWORKS_FANOUT`` — ``weaver[:backend]=width`` comma list (max concurrent worker
  tasks for that step's batch). Absent / width<=1 → no fan-out (one task, as before).
- ``BRAIDWORKS_FANOUT_UNBUDGETED`` — comma list of ``weaver[:backend]`` asserted to make
  **no rate-limited external calls** (e.g. local-DB backends), so they may fan out
  without a budget.
- ``BRAIDWORKS_FANOUT_CHUNK`` — optional ``weaver[:backend]=N`` override for entities
  per task. Default: 1 for budgeted backends (≈ per-call rate granularity), else an
  even split across ``width``.
- ``BRAIDWORKS_RATE_LIMITS`` (existing) — declares the budget that makes external
  fan-out safe.

A ``weaver:backend`` key always beats a bare ``weaver`` key (most specific wins).
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

from braidworks_arq.ratelimit import load_limits, rate_for


class FanoutConfigError(RuntimeError):
    """Fan-out was requested for a backend that has no rate budget and is not asserted
    unbudgeted — refused so an external API cannot be silently stormed."""


@dataclass(frozen=True)
class FanoutPlan:
    """How to dispatch one step's batch: at most ``width`` tasks of ``chunk`` entities."""

    width: int
    chunk: int


def _parse_widths(spec: str | None) -> dict[str, int]:
    out: dict[str, int] = {}
    for chunk in (spec or "").split(","):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        key, _, val = chunk.partition("=")
        try:
            out[key.strip()] = int(val)
        except ValueError:
            continue
    return out


def _parse_list(spec: str | None) -> set[str]:
    return {s.strip() for s in (spec or "").split(",") if s.strip()}


def _lookup(mapping: dict[str, int], weaver_id: str, backend: str) -> int | None:
    if f"{weaver_id}:{backend}" in mapping:
        return mapping[f"{weaver_id}:{backend}"]
    return mapping.get(weaver_id)


def _in(names: set[str], weaver_id: str, backend: str) -> bool:
    return f"{weaver_id}:{backend}" in names or weaver_id in names


def plan_fanout(
    weaver_id: str,
    backend: str,
    batch_size: int,
    *,
    widths: dict[str, int] | None = None,
    unbudgeted: set[str] | None = None,
    chunks: dict[str, int] | None = None,
    budgeted: bool | None = None,
) -> FanoutPlan:
    """Decide the fan-out for one step's batch. Raises :class:`FanoutConfigError` if a
    width>1 is requested for a backend with neither a rate budget nor an unbudgeted
    assertion. Args other than ids/size are read from the environment when omitted
    (the ``budgeted`` flag defaults to "is there a rate limit for this backend")."""
    widths = _parse_widths(os.environ.get("BRAIDWORKS_FANOUT")) if widths is None else widths
    unbudgeted = (
        _parse_list(os.environ.get("BRAIDWORKS_FANOUT_UNBUDGETED"))
        if unbudgeted is None
        else unbudgeted
    )
    chunks = (
        _parse_widths(os.environ.get("BRAIDWORKS_FANOUT_CHUNK")) if chunks is None else chunks
    )
    if budgeted is None:
        budgeted = rate_for(load_limits(), weaver_id, backend) is not None

    width = _lookup(widths, weaver_id, backend) or 1
    if width <= 1:
        return FanoutPlan(width=1, chunk=max(1, batch_size))

    if not budgeted and not _in(unbudgeted, weaver_id, backend):
        raise FanoutConfigError(
            f"fan-out (width={width}) requested for {weaver_id}:{backend} with no rate "
            "budget. Declare BRAIDWORKS_RATE_LIMITS for it, or list it in "
            "BRAIDWORKS_FANOUT_UNBUDGETED to assert it makes no rate-limited external calls."
        )

    chunk = _lookup(chunks, weaver_id, backend)
    if chunk is None:
        # Budgeted → 1 entity/task (≈ per-call rate granularity, smoothest burst).
        # Unbudgeted → even split so each worker gets a fair share.
        chunk = 1 if budgeted else max(1, math.ceil(batch_size / width))
    return FanoutPlan(width=width, chunk=max(1, chunk))
