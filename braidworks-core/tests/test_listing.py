"""Listing: a list that knows its own size and whether it is complete."""

import json

import pytest
from braidworks.core.listing import Listing, describe_size


def test_defaults_to_complete():
    x = Listing([1, 2])
    assert isinstance(x, list)
    assert x.total == 2
    assert x.complete is True


def test_known_total():
    x = Listing(["a"] * 25, total=321)
    assert len(x) == 25
    assert x.complete is False
    assert describe_size(x) == "25 of 321"


def test_unknown_total():
    assert describe_size(Listing(["a"] * 25, total=None, complete=False)) == "25+"
    assert describe_size(Listing([], total=None, complete=False)) == "0+"


def test_complete_describes_plain_count():
    assert describe_size(Listing([1, 2, 3])) == "3"
    assert describe_size(Listing([], total=0)) == "0"
    assert describe_size([1, 2]) is None
    assert describe_size("x") is None


@pytest.mark.parametrize(
    "items, kwargs",
    [
        ([1, 2], {"total": 1}),
        ([1], {"total": 2, "complete": True}),
        ([1], {"total": None, "complete": True}),
        ([1], {"total": None}),
    ],
)
def test_rejects_inconsistent(items, kwargs):
    with pytest.raises(ValueError):
        Listing(items, **kwargs)


def test_slice_is_plain_list():
    assert type(Listing([1, 2, 3], total=9)[:2]) is list
    assert type(Listing([1]).copy()) is list
    assert Listing([1, 2, 3], total=9)[0] == 1


def test_json_dumps_as_list():
    assert json.dumps(Listing([1], total=5)) == "[1]"


def test_repr():
    assert repr(Listing(["a", "b"], total=9)) == "['a', 'b'] (2 of 9)"
    assert repr(Listing(["a"])) == "['a']"
    assert repr(Listing(["a"], total=None, complete=False)) == "['a'] (1+)"


def test_attributes_are_read_only():
    x = Listing([1], total=4)
    with pytest.raises(AttributeError):
        x.total = 1


def test_top_level_export():
    from braidworks import Listing as Top
    from braidworks.core import Listing as Core

    assert Top is Listing and Core is Listing


def test_survives_copy_and_pickle():
    import copy
    import pickle

    x = Listing([1, 2], total=5)
    for y in (copy.copy(x), copy.deepcopy(x), pickle.loads(pickle.dumps(x))):
        assert isinstance(y, Listing) and y == [1, 2] and y.total == 5 and not y.complete
