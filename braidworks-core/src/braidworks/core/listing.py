"""``Listing`` — a list result that knows its own size.

A source can hand back all of a list, a prefix of a list whose size it reports, or
a prefix of unknown size (it stopped early). ``Listing`` is a plain ``list`` that
records which, so readers never have to combine a list with a sibling count:

=====================  ==================  ==========================================
``complete``           ``total``           meaning
=====================  ==================  ==========================================
``True``               ``len(listing)``    the whole list
``False``              an ``int > len``    a prefix of a list of known size (25 of 321)
``False``              ``None``            stopped early; at least ``len`` items (25+)
=====================  ==================  ==========================================

It behaves as a ``list`` everywhere (iteration, ``json.dumps``, pandas). Slicing or
copying returns a plain ``list``, because a slice is no longer "a prefix of N".
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class _Unset:
    """The default ``total``: the number of items given."""

    def __repr__(self) -> str:
        return "len(items)"


_UNSET: Any = _Unset()


class Listing(list):
    """A list plus its true ``total`` (``None`` = unknown) and whether it is ``complete``."""

    __slots__ = ("_complete", "_total")

    def __init__(
        self,
        items: Iterable[Any] = (),
        *,
        total: int | None = _UNSET,
        complete: bool | None = None,
    ) -> None:
        super().__init__(items)
        n = len(self)
        if total is _UNSET:
            total = n
        if complete is None:
            if total is None:
                raise ValueError("Listing(total=None) needs complete=False: an unknown size")
            complete = total == n
        if total is None:
            if complete:
                raise ValueError("a complete Listing has a known total")
        elif total < n:
            raise ValueError(f"Listing total {total} is smaller than its {n} items")
        elif complete and total != n:
            raise ValueError(f"a complete Listing of {n} items cannot have total {total}")
        elif not complete and total == n:
            raise ValueError(f"a partial Listing of {n} items needs a total above {n}")
        self._total = total
        self._complete = bool(complete)

    @property
    def total(self) -> int | None:
        """The list's true size; ``None`` when the source could not tell."""
        return self._total

    @property
    def complete(self) -> bool:
        """Whether this holds every item (``len(listing) == total``)."""
        return self._complete

    def __getitem__(self, index):  # type: ignore[override]
        value = super().__getitem__(index)
        return list(value) if isinstance(index, slice) else value

    def copy(self) -> list:  # type: ignore[override]
        """A plain ``list`` of the items (a copy is no longer "a prefix of N")."""
        return list(self)

    def __repr__(self) -> str:
        base = list.__repr__(self)
        return base if self._complete else f"{base} ({describe_size(self)})"


def describe_size(value: Any) -> str | None:
    """``"25 of 321"`` / ``"25+"`` / ``"321"`` for a ``Listing``; ``None`` for anything else."""
    if not isinstance(value, Listing):
        return None
    n = len(value)
    if value.complete:
        return str(n)
    if value.total is None:
        return f"{n}+"
    return f"{n} of {value.total}"
