"""Self-test: the shipped contract mixins pass against an in-repo fake weaver.

This both exercises the mixins and demonstrates the intended subclassing pattern.
"""

from __future__ import annotations

from braidworks.core.strand import Strand, StrandSet
from braidworks.testing import CacheFingerprintTests, WeaverOrderContractTests

from helpers import ScriptedWeaver, ok_result, resolve_name_capability

ID = "ncbi.taxon.id"
NAMES = ["Homo sapiens", "Mus musculus", "Escherichia coli", "Danio rerio", "Gallus gallus"]


def _deterministic_resolver(strand_set, backend, requested):
    name = strand_set.get("organism.name").value
    return ok_result(requested, Strand(ID, abs(hash(name)) % 100_000), backend=backend)


class TestScriptedWeaverOrder(WeaverOrderContractTests):
    capability_id = "ncbi.resolve_name"
    minimal_outputs = frozenset({ID})

    def make_weaver(self):
        return ScriptedWeaver(_deterministic_resolver)

    def sample_strand_sets(self):
        return [
            StrandSet.from_strands(f"e{i}", [Strand("organism.name", n)])
            for i, n in enumerate(NAMES)
        ]


class TestResolveNameCacheFingerprint(CacheFingerprintTests):
    capability = resolve_name_capability()
    consumed_values_a = {"organism.name": "Homo sapiens"}
    consumed_values_b = {"organism.name": "Mus musculus"}
    # group_subset="core" / group_superset="lineage" defaults match this capability.
