"""Strands carry list size; the mapper unpacks Listing and derives .count aliases."""

from braidworks.core.capability import Capability, OutputGroup
from braidworks.core.listing import Listing
from braidworks.core.mapper import map_lookup, map_resolver
from braidworks.core.records import Candidate, LookupRecord, MatchStatus, ResolverRecord
from braidworks.core.strand import Strand, StrandSet


def _cap(*, set_outputs=frozenset(), totals=None) -> Capability:
    outs = frozenset({"a.ids", "a.count", "a.names"})
    return Capability(
        id="list_a",
        consumes=frozenset({"a.query"}),
        produces=outs,
        output_groups=(OutputGroup(id="all", outputs=outs),),
        backends=("api",),
        set_outputs=frozenset(set_outputs),
        totals=dict(totals or {}),
    )


def _map(values, cap, requested=frozenset({"a.ids", "a.count", "a.names"})):
    return map_lookup(
        LookupRecord(query={}, found=True, values=values),
        capability=cap,
        requested_outputs=requested,
        backend="api",
        weaver_version="1",
        weaver_id="w",
    )


def _by_type(result):
    return {s.type_id: s for s in result.strands}


def test_strand_json_omits_defaults():
    assert set(Strand("x", [1]).to_json()) == {
        "type_id",
        "value",
        "confidence",
        "provenance",
        "metadata",
    }
    partial = Strand("x", [1], total=5, complete=False)
    back = Strand.from_json(partial.to_json())
    assert (back.total, back.complete, back.value) == (5, False, [1])


def test_as_value_wraps_only_sized_strands():
    assert type(Strand("x", [1]).as_value()) is list
    wrapped = Strand("x", [1], total=5, complete=False).as_value()
    assert isinstance(wrapped, Listing) and wrapped.total == 5
    assert isinstance(Strand("x", [1, 2], total=2).as_value(), Listing)


def test_strandset_round_trip_keeps_partial():
    ss = StrandSet.from_strands("e", [Strand("x", ["a"], total=5, complete=False)])
    value = StrandSet.from_json(ss.to_json()).get("x").as_value()
    assert isinstance(value, Listing)
    assert value.total == 5 and not value.complete


def test_mapper_unpacks_listing_and_derives_count():
    got = _by_type(_map({"a.ids": Listing(["p"], total=7)}, _cap(totals={"a.ids": "a.count"})))
    assert type(got["a.ids"].value) is list and got["a.ids"].value == ["p"]
    assert (got["a.ids"].total, got["a.ids"].complete) == (7, False)
    assert got["a.count"].value == 7


def test_mapper_omits_alias_when_total_unknown():
    listing = Listing(["p"], total=None, complete=False)
    got = _by_type(_map({"a.ids": listing}, _cap(totals={"a.ids": "a.count"})))
    assert "a.count" not in got
    assert got["a.ids"].total is None and got["a.ids"].complete is False


def test_mapper_alias_not_emitted_unless_requested():
    got = _by_type(
        _map(
            {"a.ids": Listing(["p"], total=7)},
            _cap(totals={"a.ids": "a.count"}),
            requested=frozenset({"a.ids"}),
        )
    )
    # Same group, so the group computes a.count too; the alias follows `allowed`.
    assert got["a.count"].value == 7


def test_mapper_explicit_count_wins():
    cap = _cap(totals={"a.ids": "a.count"})
    result = _map({"a.ids": Listing(["p"], total=7), "a.count": 7}, cap)
    assert [s.type_id for s in result.strands].count("a.count") == 1


def test_set_output_defaults_complete():
    got = _by_type(_map({"a.ids": ["p", "q"], "a.names": ["P"]}, _cap(set_outputs={"a.ids"})))
    assert (got["a.ids"].total, got["a.ids"].complete) == (2, True)
    assert got["a.names"].total is None


def test_resolver_and_candidates_unpack():
    cap = _cap(totals={"a.ids": "a.count"})
    args = {
        "capability": cap,
        "requested_outputs": frozenset({"a.ids", "a.count"}),
        "backend": "api",
        "weaver_version": "1",
        "weaver_id": "w",
    }
    ok = map_resolver(
        ResolverRecord(
            query={}, status=MatchStatus.RESOLVED, values={"a.ids": Listing(["p"], total=3)}
        ),
        **args,
    )
    got = _by_type(ok)
    assert got["a.ids"].total == 3 and got["a.count"].value == 3

    amb = map_resolver(
        ResolverRecord(
            query={},
            status=MatchStatus.AMBIGUOUS,
            candidates=[Candidate(values={"a.ids": Listing(["p"], total=4)})],
        ),
        **args,
    )
    strand = {s.type_id: s for s in amb.candidates[0].strands}["a.ids"]
    assert type(strand.value) is list and strand.total == 4
