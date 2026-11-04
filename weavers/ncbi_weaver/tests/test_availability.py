"""Local-only construction retains diagnostic knowledge of API operations."""

import pytest
from braidworks.core import Braider, BraidRegistry
from braidworks.core.exceptions import BackendUnavailable, NoPlanError, UnsupportedCapability
from ncbi_weaver import vocab
from ncbi_weaver.weaver import NCBITaxonWeaver


class InertLocal:
    name = "local"

    def is_configured(self):
        return True

    async def resolve(self, *args, **kwargs):
        raise AssertionError("must fail before source calls")


def test_local_children_and_disabled_gene_routes():
    weaver = NCBITaxonWeaver({"local": InertLocal()})
    registry = BraidRegistry()
    registry.register(weaver)
    planner = Braider(registry)
    plan = planner.plan(frozenset({"ncbi.taxon.id"}), frozenset({"ncbi.taxon.children_records"}))
    assert plan.steps[0].primary_backend == "local"
    with pytest.raises(NoPlanError, match="ncbi.describe_gene.*not enabled: api"):
        planner.plan(frozenset({"gene.ncbi.id"}), frozenset({"gene.symbol"}))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cap,backend,error",
    [
        (vocab.DESCRIBE_GENE, "api", BackendUnavailable),
        (vocab.DESCRIBE_GENE, "local", BackendUnavailable),
        (vocab.DESCRIBE_TAXON_HISTORY, "api", BackendUnavailable),
        ("nonexistent", "local", UnsupportedCapability),
    ],
)
async def test_dispatch_rejects_before_source_calls(cap, backend, error):
    weaver = NCBITaxonWeaver({"local": InertLocal()})
    with pytest.raises(error):
        await weaver.execute_batch(cap, [], requested_outputs=frozenset(), backend=backend)
