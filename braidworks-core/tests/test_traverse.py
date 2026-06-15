"""Traversal fan-out: chain a weave THROUGH a same-type relationship.

``run_traversed`` runs a fan capability (e.g. ``list_orthologs`` gene id -> gene ids),
re-roots on each produced value, and plans ``want`` from each child — the thing the
type planner can't route on its own because the produced type equals the input type.
"""

from __future__ import annotations

import pytest

from braidworks.core.capability import Capability, OutputGroup
from braidworks.core.exceptions import NoPlanError
from braidworks.core.executor import ExpandPolicy
from braidworks.core.planner import Braider
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import Strand, StrandSet
from braidworks.core.traverse import (
    fan_capabilities,
    relationship_name,
    resolve_traversal,
    run_traversed,
)

from helpers import ScriptedWeaver, simple_capability

GENE = "gene.ncbi.id"
SYMBOL = "gene.symbol"
COUNT = "gene.ortholog.count"
ORTHOLOGS = "ncbi.list_orthologs"
DESCRIBE = "ncbi.describe_gene"


def _orthologs_cap() -> Capability:
    produces = frozenset({GENE, COUNT})
    return Capability(
        id=ORTHOLOGS,
        consumes=frozenset({GENE}),
        produces=produces,
        output_groups=(OutputGroup(id="g", outputs=produces),),
        backends=("api",),
        set_outputs=frozenset({GENE}),
    )


def _ortholog_result(ortholog_ids: list[str]) -> WeaveResult:
    return WeaveResult(
        capability_id=ORTHOLOGS,
        weaver_version="1.0.0",
        backend_used="api",
        computed_groups=frozenset({"g"}),
        status=WeaveStatus.OK,
        strands=(Strand(GENE, ortholog_ids), Strand(COUNT, len(ortholog_ids))),
    )


def _describe_result(ss: StrandSet, backend: str, requested) -> WeaveResult:
    gene = ss.get(GENE).value
    return WeaveResult(
        capability_id=DESCRIBE,
        weaver_version="1.0.0",
        backend_used=backend,
        computed_groups=frozenset({"g"}),
        status=WeaveStatus.OK,
        strands=(Strand(SYMBOL, f"SYM-{gene}"),),
    )


def _registry() -> BraidRegistry:
    reg = BraidRegistry()
    reg.register(
        ScriptedWeaver(
            lambda ss, b, r: _ortholog_result(["100", "200", "300"]),
            capability=_orthologs_cap(),
            weaver_id="ncbi",
        )
    )
    reg.register(
        ScriptedWeaver(
            _describe_result,
            capability=simple_capability(DESCRIBE, {GENE}, {SYMBOL}, backends=("api",)),
            weaver_id="desc",
        )
    )
    return reg


def _inputs(gene: str = "7157") -> list[StrandSet]:
    return [StrandSet.from_strands("e0", [Strand(GENE, gene)])]


# --- relationship resolution ---------------------------------------------------

def test_relationship_name_strips_list_prefix():
    assert relationship_name("ncbi.list_orthologs") == "orthologs"
    assert relationship_name("ncbi.list_children") == "children"
    assert relationship_name("ncbi.describe_gene") == "describe_gene"  # no list_ → bare local


def test_fan_capabilities_lists_only_set_output_caps():
    fans = fan_capabilities(_registry())
    assert fans == [("orthologs", "ncbi", ORTHOLOGS)]  # describe_gene has no set outputs


def test_resolve_by_relationship_noun():
    assert resolve_traversal(_registry(), "orthologs") == ("ncbi", ORTHOLOGS)


def test_resolve_by_full_capability_id():
    assert resolve_traversal(_registry(), ORTHOLOGS) == ("ncbi", ORTHOLOGS)


def test_resolve_non_fan_capability_is_clear_error():
    with pytest.raises(NoPlanError, match="not a fan capability"):
        resolve_traversal(_registry(), DESCRIBE)


def test_resolve_unknown_token_lists_available():
    with pytest.raises(NoPlanError, match="orthologs"):
        resolve_traversal(_registry(), "paralogs")


def test_resolve_ambiguous_relationship_points_to_capability_ids():
    reg = _registry()
    reg.register(
        ScriptedWeaver(
            lambda ss, b, r: _ortholog_result(["9"]),
            capability=Capability(
                id="ensembl.list_orthologs",
                consumes=frozenset({GENE}),
                produces=frozenset({GENE}),
                output_groups=(OutputGroup(id="g", outputs=frozenset({GENE})),),
                backends=("api",),
                set_outputs=frozenset({GENE}),
            ),
            weaver_id="ensembl",
        )
    )
    with pytest.raises(NoPlanError, match="ambiguous"):
        resolve_traversal(reg, "orthologs")


# --- the orchestration ---------------------------------------------------------

async def test_describe_each_ortholog():
    res = await run_traversed(
        _registry(),
        _inputs("7157"),
        [("ncbi", ORTHOLOGS)],
        frozenset({SYMBOL}),
    )
    assert len(res.resolved) == 3
    # each child describes its OWN ortholog id, not the seed gene 7157
    assert sorted(s.get(SYMBOL).value for s in res.resolved) == [
        "SYM-100", "SYM-200", "SYM-300",
    ]
    # lineage regroups every child to the original query
    assert {s.parent_id for s in res.resolved} == {"e0"}
    assert 7157 not in {s.get(GENE).value for s in res.resolved}


async def test_no_want_returns_the_fanned_children():
    res = await run_traversed(
        _registry(), _inputs("7157"), [("ncbi", ORTHOLOGS)], frozenset()
    )
    # gene.ncbi.id canonicalizes to int
    assert sorted(s.get(GENE).value for s in res.resolved) == [100, 200, 300]


async def test_top_k_limits_the_fan():
    res = await run_traversed(
        _registry(),
        _inputs("7157"),
        [("ncbi", ORTHOLOGS)],
        frozenset({SYMBOL}),
        expand_policy=ExpandPolicy.top_k(2),
    )
    assert len(res.resolved) == 2


async def test_plan_capability_builds_one_step_braid():
    braid = Braider(_registry()).plan_capability("ncbi", ORTHOLOGS)
    assert len(braid.steps) == 1
    step = braid.steps[0]
    assert step.capability_id == ORTHOLOGS
    assert step.input_types == frozenset({GENE})
    assert step.primary_backend == "api"
