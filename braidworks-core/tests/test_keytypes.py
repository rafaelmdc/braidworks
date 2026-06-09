"""Canonical shared-key value types: Strand normalizes on construction."""

from __future__ import annotations

from braidworks.core import Capability, OutputGroup, Strand, StrandSet, canonicalize, compute_cache_key


def test_int_keys_coerce_digit_strings():
    assert Strand("ncbi.taxon.id", "1578").value == 1578
    assert Strand("ncbi.taxon.id", 1578).value == 1578
    assert isinstance(Strand("ncbi.taxon.id", "1578").value, int)


def test_str_keys_coerce_numbers():
    assert Strand("organism.scientific_name", 562).value == "562"
    assert Strand("organism.scientific_name", "Escherichia coli").value == "Escherichia coli"


def test_unregistered_key_passes_through():
    assert Strand("my.private.key", "abc").value == "abc"
    assert Strand("my.private.key", 7).value == 7


def test_uncoercible_and_none_are_left_alone():
    assert Strand("ncbi.taxon.id", "not-a-number").value == "not-a-number"
    assert Strand("ncbi.taxon.id", None).value is None
    # booleans are never reinterpreted as ints
    assert Strand("ncbi.taxon.id", True).value is True


def test_canonicalize_is_total_and_pure():
    assert canonicalize("ncbi.taxon.id", "42") == 42
    assert canonicalize("unknown.key", object) is object


def test_int_vs_str_taxid_share_one_cache_fingerprint():
    """The whole point: 1578 and "1578" must produce the same input_fingerprint."""
    cap = Capability(
        id="x.resolve",
        consumes=frozenset({"ncbi.taxon.id"}),
        produces=frozenset({"out.value"}),
        output_groups=(OutputGroup(id="core", outputs=frozenset({"out.value"})),),
        backends=("local",),
    )
    key_args = dict(
        weaver_id="x", weaver_version="1.0.0", backend="local", backend_fingerprint="fp"
    )
    as_int = compute_cache_key(
        cap, StrandSet.from_strands("a", [Strand("ncbi.taxon.id", 1578)]), **key_args
    )
    as_str = compute_cache_key(
        cap, StrandSet.from_strands("b", [Strand("ncbi.taxon.id", "1578")]), **key_args
    )
    assert as_int.input_fingerprint == as_str.input_fingerprint
