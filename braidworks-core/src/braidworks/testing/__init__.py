"""Reusable contract-test mixins for weaver authors.

Import these into your weaver's test suite and subclass them so pytest collects
the shared assertions against your concrete weaver::

    from braidworks.testing import WeaverOrderContractTests, CacheFingerprintTests

    class TestNCBIOrder(WeaverOrderContractTests):
        capability_id = "ncbi.resolve_name"
        minimal_outputs = frozenset({"ncbi.taxon.id"})

        def make_weaver(self):
            return NCBITaxonWeaver(db_path=TEST_DB)

        def sample_strand_sets(self):
            return [StrandSet.from_strands(...), ...]  # >= 5 distinct inputs

The mixin class names end in ``Tests`` (not ``Test*``) so pytest does not try to
collect them directly — only your subclasses are collected.
"""

from braidworks.testing.contract import (
    CacheFingerprintTests,
    WeaverOrderContractTests,
)

__all__ = ["CacheFingerprintTests", "WeaverOrderContractTests"]
