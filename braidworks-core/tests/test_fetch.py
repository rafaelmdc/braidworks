"""Tests for the ``fetch`` convenience facade.

These drive a real registry (a ``ScriptedWeaver`` resolving ``ncbi.taxon.id`` ->
``microbe.metabolism.reactions``) through ``fetch``/``async_fetch``, so the facade's
plan -> execute -> unwrap -> bucketing logic is exercised end-to-end without touching
entry-point discovery or the network.
"""

from __future__ import annotations

from braidworks.core import async_fetch, fetch
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import Strand

from helpers import ScriptedWeaver, simple_capability

WANT = "microbe.metabolism.reactions"
CAP = simple_capability("agora.reactions", {"ncbi.taxon.id"}, {WANT})

# A tiny "database": which taxid has which reactions. Missing ids => NO_MATCH.
_DB = {"853": ["ACGAMK", "PGK"], "1680": ["FBA"]}


def _resolver(strand_set, backend, requested):
    # ncbi.taxon.id canonicalizes to int, so key the lookup by its string form.
    taxid = str(strand_set.get("ncbi.taxon.id").value)
    reactions = _DB.get(taxid)
    if reactions is None:
        return WeaveResult(
            capability_id="agora.reactions",
            weaver_version="1.0.0",
            backend_used=backend,
            computed_groups=frozenset({"g"}),
            status=WeaveStatus.NO_MATCH,
        )
    return WeaveResult(
        capability_id="agora.reactions",
        weaver_version="1.0.0",
        backend_used=backend,
        computed_groups=frozenset({"g"}),
        status=WeaveStatus.OK,
        strands=(Strand(WANT, reactions),),
    )


def _registry() -> BraidRegistry:
    reg = BraidRegistry()
    reg.register(ScriptedWeaver(_resolver, capability=CAP, weaver_id="agora"))
    return reg


async def test_async_fetch_resolves_and_reports_gaps():
    res = await async_fetch(WANT, ids=["853", "1680", "999"], registry=_registry())

    assert res.get("853")[WANT] == ["ACGAMK", "PGK"]
    assert res.get("1680")[WANT] == ["FBA"]
    # A taxid with no model is absent, not silently missing — this is the datum a
    # coverage mask needs.
    assert res.unresolved == ["999"]
    assert "999" not in res.resolved


async def test_column_helper_returns_id_to_value_map():
    res = await async_fetch(WANT, ids=["853", "1680"], registry=_registry())
    assert res.column(WANT) == {"853": ["ACGAMK", "PGK"], "1680": ["FBA"]}


async def test_duplicate_ids_collapse():
    res = await async_fetch(WANT, ids=["853", "853"], registry=_registry())
    assert list(res.resolved) == ["853"]
    assert res.unresolved == []


def test_sync_fetch_wrapper_runs_its_own_loop():
    # Plain (non-async) test: the sync wrapper must spin up its own event loop.
    res = fetch(WANT, ids=["853", "999"], registry=_registry())
    assert res.get("853")[WANT] == ["ACGAMK", "PGK"]
    assert res.unresolved == ["999"]
